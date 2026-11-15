#!/usr/bin/env python3
"""Course-level audio: plan every unit's clips, synthesize them once, build MP3 listening episodes.

    course_audio.py plan     --course course.json                         # no network: write plan.json, list missing clips
    course_audio.py synth    --course course.json --confirm-external-tts  # synthesize missing clips into the cache
    course_audio.py episodes --course course.json --confirm-external-tts  # one MP3 per unit (needs ffmpeg)
    course_audio.py episodes --course course.json --confirm-external-tts --kind examples --repeat 2
                                                                          # only the example sentences, each repeated

Clip ids use the same scheme as embed_audio.build_plan, so a cache filled by either tool serves both.
Hosted synthesis sends the selected learner text to the Edge TTS service: obtain the user's approval first.
See references/course-app.md for course.json and the listening design.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_audio import AudioError, explanation_blocks, explanation_speech, lesson_plan, require, synthesize  # noqa: E402
import language  # noqa: E402
import speech  # noqa: E402
import study_pack  # noqa: E402

BYTES_PER_SECOND = 6000   # edge-tts delivers 48 kbit/s constant-bitrate MP3
STEP = 0.4                # silence granularity in seconds
COURSE_KEYS = {"title", "subtitle", "narration", "more_examples", "dialogues", "translations", "voices", "cache",
               "episodes_dir", "new_per_day", "private_terms", "units"}
MORE_USES = ("daily", "writing", "exam")          # where an extra grammar example is used: everyday life, writing, the exam
DIALOGUE_MIN_LINES = 6                            # a dialogue: a real conversation, not an exchange of two sentences
# What a translations file gives per card, beside the English in the lesson (see references/course-app.md):
# a word: its meaning, its forms line (only where that has English in it) and one translation per example;
# a grammar point: one translation per example and per extra example, and its explanation (where it has an English one);
# a phrase: its meaning, when to use it, its register and variants (where it has them) and one translation per example;
# a unit with a story: one translation per paragraph ("story").
TRANSLATION_FIELDS = {"vocabulary": {"gloss", "forms", "ex"}, "grammar": {"ex", "more", "explain"},
                      "redemittel": {"gloss", "when", "register", "variants", "ex"}}


def load_course(path):
    path = Path(path).resolve()
    course = json.loads(path.read_text(encoding="utf-8-sig"))
    base = path.parent
    unknown = sorted(set(course) - COURSE_KEYS)   # a misspelt key would silently fall back to a default
    require(not unknown, f"course.json has unknown key(s) {', '.join(unknown)}; see references/course-app.md")
    require(isinstance(course.get("units"), list) and course["units"], "course.json needs a non-empty units list")
    course["title"] = course.get("title") or "Course"
    narration = course.get("narration")
    course["narration"] = json.loads((base / narration).read_text(encoding="utf-8-sig")) if narration else {}
    more = course.get("more_examples")
    course["more_examples"] = json.loads((base / more).read_text(encoding="utf-8-sig")) if more else {}
    talk = course.get("dialogues")
    course["dialogues"] = json.loads((base / talk).read_text(encoding="utf-8-sig")) if talk else {}
    files = course.get("translations") or {}
    require(isinstance(files, dict), 'translations: {"<language code>": "<file>"}, for example {"ar": "translations_ar.json"}')
    course["translations"] = {code: json.loads((base / name).read_text(encoding="utf-8-sig")) for code, name in sorted(files.items())}
    course["cache"] = (base / course.get("cache", "_work/audio")).resolve()
    course["episodes_dir"] = (base / course.get("episodes_dir", "Audio")).resolve()
    course["private_terms"] = [str(term) for term in course.get("private_terms", [])]
    for term in course["private_terms"]:          # names of the source that must never reach learner output
        require(not exact_term(course["title"] + " " + course.get("subtitle", ""), term),
                f"course title or subtitle names the private source term {term!r}")
    seen = set()
    for unit in course["units"]:
        for key in ("id", "label", "lesson", "sheet"):
            require(unit.get(key), f"unit is missing {key}: {unit}")
        require(re.fullmatch(r"[A-Za-z0-9_-]+", unit["id"]) is not None, f"unit id must be a simple token: {unit['id']}")
        require(unit["id"] not in seen, f"duplicate unit id {unit['id']}")
        require("group" not in unit or (isinstance(unit["group"], str) and unit["group"].strip()),
                f"unit {unit['id']}: group must be a short text, such as the book's name")
        seen.add(unit["id"])
        unit["lesson"] = (base / unit["lesson"]).resolve()
        unit["sheet"] = (base / unit["sheet"]).resolve()
        require(unit["lesson"].is_file(), f"lesson file not found: {unit['lesson']}")
        require(unit["sheet"].is_file(), f"sheet file not found: {unit['sheet']}")
    groups = [unit.get("group") for unit in course["units"]]          # books in one course, each a run of units
    require(all(groups) or not any(groups), "give every unit a group, or none")
    starts = [group for index, group in enumerate(groups) if group and (index == 0 or groups[index - 1] != group)]
    require(len(starts) == len(set(starts)), "the units of a group must follow each other")
    codes = {language.code_of(json.loads(unit["lesson"].read_text(encoding="utf-8-sig")).get("target_language", "de"))
             for unit in course["units"]}
    require(len(codes) == 1, f"all units of a course need one target language, not {', '.join(sorted(codes))}")
    try:
        course["profile"] = language.profile(codes.pop())
    except language.LanguageError as error:
        raise AudioError(str(error)) from error
    speech.use(course["profile"])                 # the course's language: its voice, words and notation
    course["voices"] = {"de": course["profile"]["voice"], "en": speech.DEFAULT_VOICES["en"],
                        **language.narrator(course["profile"]), **(course.get("voices") or {})}
    check_more_examples(course)
    check_dialogues(course)
    check_translations(course)
    for code in course["translations"]:           # each translation language speaks with its own profile's voice
        course["voices"].setdefault(code, language.profile(code)["voice"])
    return course


def _translated(text, where, latin_free, lines=False):
    """A translated text: not empty, its «…» closed in turn, one line (an explanation: lines), and in a language
    written without Latin letters every Latin word inside «…», where the target-language voice speaks it."""
    require(isinstance(text, str) and text.strip(), f"{where}: an empty or missing translation")
    require(lines or "\n" not in text, f"{where}: one line")
    require(balanced_marks(text), f"{where}: «…» do not close in turn")
    if latin_free:
        outside = re.sub(r"«[^«»]*»", "", text)
        found = re.findall(r"[A-Za-zÄÖÜäöüß]+", outside)
        require(not found, f"{where}: Latin letters outside «…» ({', '.join(found[:3])}): mark the target-language words «…»")


def check_translations(course):
    """translations: per language a file with, per unit, the translation of every English text of its cards and its
    story (TRANSLATION_FIELDS); every unit and card is covered, so a learner never meets English in that language."""
    if not course["translations"]:
        return
    lessons = {u["id"]: json.loads(u["lesson"].read_text(encoding="utf-8-sig")) for u in course["units"]}
    for code, data in course["translations"].items():
        require(re.fullmatch(r"[a-z]{2,3}", code) is not None and code not in ("en", course["profile"]["code"]),
                f"translations: {code!r} is not a language to translate into (English is the lesson's own)")
        try:
            prof = language.profile(code)
        except language.LanguageError as error:
            raise AudioError(f"translations {code}: {error}") from error
        latin_free = not re.search(r"[A-Za-z]", prof.get("native", "A"))
        require(isinstance(data, dict), f"translations {code}: an object with one entry per unit")
        unknown = sorted(set(data) - set(lessons))
        require(not unknown, f"translations {code}: unknown unit(s) {', '.join(unknown)}")
        for uid, lesson in lessons.items():
            unit = data.get(uid)
            require(isinstance(unit, dict), f"translations {code}: unit {uid} is missing")
            records = {rec["id"]: (section, rec) for section in TRANSLATION_FIELDS for rec in lesson[section]}
            extra = sorted(set(unit) - set(records) - {"story", "dialogue"})
            require(not extra, f"translations {code} {uid}: unknown card(s) {', '.join(extra)}")
            for rid, (section, rec) in records.items():
                where, item = f"translations {code} {uid} {rid}", unit.get(rid)
                require(isinstance(item, dict), f"{where}: missing")
                unknown = sorted(set(item) - TRANSLATION_FIELDS[section])
                require(not unknown, f"{where}: unknown field(s) {', '.join(unknown)}")
                need = {"ex"} | ({"gloss"} if section != "grammar" else set())
                if section == "redemittel":
                    need |= {"when"} | ({"register"} if rec.get("register") else set()) | ({"variants"} if rec.get("variants") else set())
                if section == "grammar":
                    told = course["narration"].get(uid, {}).get(rid)
                    if (isinstance(told, dict) and told.get("en")) or isinstance(told, str):
                        need.add("explain")
                    if course["more_examples"].get(uid, {}).get(rid):
                        need.add("more")
                missing = sorted(need - set(item))
                require(not missing, f"{where}: missing {', '.join(missing)}")
                counts = {"ex": len(rec["examples"]), "variants": len(rec.get("variants", [])),
                          "more": len(course["more_examples"].get(uid, {}).get(rid, []))}
                for field, value in item.items():
                    if field in counts:
                        require(isinstance(value, list) and len(value) == counts[field],
                                f"{where}: {field} needs {counts[field]} translation(s), one per English one")
                        for index, text in enumerate(value):
                            _translated(text, f"{where} {field} [{index}]", latin_free)
                    else:
                        _translated(value, f"{where} {field}", latin_free, lines=field == "explain")
            paragraphs = (lesson.get("story") or {}).get("paragraphs", [])
            story = unit.get("story", [])
            require(isinstance(story, list) and len(story) == len(paragraphs),
                    f"translations {code} {uid}: story needs {len(paragraphs)} paragraph translation(s)")
            for index, text in enumerate(story):
                _translated(text, f"translations {code} {uid} story [{index}]", latin_free)
            talk, told = course["dialogues"].get(uid), unit.get("dialogue")
            where = f"translations {code} {uid} dialogue"
            if not talk:
                require(told is None, f"{where}: the unit has no dialogue")
                continue
            require(isinstance(told, dict) and set(told) == ({"scene", "lines"} if talk.get("scene") else {"lines"}),
                    f'{where}: {{"scene": its translation, "lines": one per line}}' if talk.get("scene")
                    else f'{where}: {{"lines": one translation per line}}')
            if talk.get("scene"):
                _translated(told["scene"], f"{where} scene", latin_free)
            require(isinstance(told["lines"], list) and len(told["lines"]) == len(talk["lines"]),
                    f"{where}: lines needs {len(talk['lines'])} translation(s), one per line")
            for index, text in enumerate(told["lines"]):
                _translated(text, f"{where} line [{index}]", latin_free)


def unit_translations(course, uid):
    """{language: what the translations file gives for this unit}, in the course's order of languages."""
    return {code: data.get(uid, {}) for code, data in course["translations"].items()}


def check_more_examples(course):
    """more_examples: per unit and grammar point, a list of extra examples, each {"use": daily, writing or exam,
    "de": the sentence, "en": its English, "targets": the parts of "de" that show the grammar (marked like any example)}."""
    lessons = {u["id"]: json.loads(u["lesson"].read_text(encoding="utf-8-sig")) for u in course["units"]}
    for uid, points in course["more_examples"].items():
        require(uid in lessons, f"more_examples names an unknown unit: {uid}")
        grammar = {record["id"] for record in lessons[uid]["grammar"]}
        for gid, items in points.items():
            require(gid in grammar, f"more_examples names an unknown grammar point: {uid} {gid}")
            require(isinstance(items, list) and items, f"more_examples {uid} {gid}: a list of examples")
            for index, item in enumerate(items):
                where = f"more_examples {uid} {gid} [{index}]"
                require(isinstance(item, dict) and set(item) == {"use", "de", "en", "targets"},
                        f'{where}: {{"use", "de", "en", "targets"}}')
                require(item["use"] in MORE_USES, f"{where}: use is one of {', '.join(MORE_USES)}")
                try:
                    study_pack.target_spans(item, where)     # every target is in the sentence, as a whole word
                except study_pack.PackError as error:
                    raise AudioError(str(error)) from error


def check_dialogues(course):
    """dialogues: per unit one everyday conversation to listen to, repeat and act out (see references/course-app.md):
    {"title", "scene": {"de", "en"} (optional), "people": {name: voice} (two people, two voices of the course's
    language), "lines": [{"who": a name, "de", "en", "uses": [{"card", "form"}]}]}. A use names a card of the unit
    and the exact form the line uses (a whole word or phrase); words and phrases are underlined, so they must not
    overlap. No line names the source (private_terms)."""
    lessons = {u["id"]: json.loads(u["lesson"].read_text(encoding="utf-8-sig")) for u in course["units"]}
    lang = course["profile"]["code"]
    for uid, talk in course["dialogues"].items():
        where = f"dialogues {uid}"
        require(uid in lessons, f"dialogues names an unknown unit: {uid}")
        require(isinstance(talk, dict) and {"title", "people", "lines"} <= set(talk) <= {"title", "scene", "people", "lines"},
                f'{where}: {{"title", "scene", "people", "lines"}} (scene is optional)')
        require(isinstance(talk["title"], str) and talk["title"].strip(), f"{where}: a title")
        texts = [talk["title"]]
        if "scene" in talk:
            scene = talk["scene"]
            require(isinstance(scene, dict) and set(scene) == {"de", "en"}
                    and all(isinstance(v, str) and v.strip() and "\n" not in v for v in scene.values()),
                    f'{where}: scene is {{"de": the situation in the course\'s language, "en": in English}}')
            texts.append(scene["de"])
        people = talk["people"]
        require(isinstance(people, dict) and len(people) == 2 and all(isinstance(n, str) and n.strip() for n in people),
                f"{where}: people names the two speakers, {{name: voice}}")
        voices = list(people.values())
        require(all(isinstance(v, str) and v.startswith(lang + "-") for v in voices) and voices[0] != voices[1],
                f"{where}: each speaker needs their own {lang}-… voice, for example de-DE-KatjaNeural and de-DE-ConradNeural")
        lines = talk["lines"]
        require(isinstance(lines, list) and len(lines) >= DIALOGUE_MIN_LINES, f"{where}: at least {DIALOGUE_MIN_LINES} lines")
        sections = {rec["id"]: section for section in ("vocabulary", "grammar", "redemittel") for rec in lessons[uid][section]}
        for index, line in enumerate(lines):
            at = f"{where} line [{index}]"
            require(isinstance(line, dict) and {"who", "de", "en"} <= set(line) <= {"who", "de", "en", "uses"},
                    f'{at}: {{"who", "de", "en", "uses"}}')
            require(line["who"] in people, f"{at}: who is one of {', '.join(people)}")
            for key in ("de", "en"):
                require(isinstance(line[key], str) and line[key].strip() and "\n" not in line[key], f"{at}: {key} is one line of text")
            texts.append(line["de"])
            marks = []
            for use in line.get("uses", []):
                require(isinstance(use, dict) and set(use) == {"card", "form"}, f'{at}: a use is {{"card", "form"}}')
                require(use["card"] in sections, f"{at}: uses unknown card {use['card']}")
                found = study_pack.exact_matches(line["de"], use["form"])
                require(found, f"{at}: the form {use['form']!r} of {use['card']} is absent or inside another word")
                if sections[use["card"]] != "grammar":         # words and phrases are underlined
                    marks.append((found[0].start(), found[0].end()))
            marks.sort()
            require(all(a[1] <= b[0] for a, b in zip(marks, marks[1:])), f"{at}: underlined words and phrases overlap")
        require(set(people) == {line["who"] for line in lines}, f"{where}: both people speak")
        for text in texts:
            for term in course["private_terms"]:
                require(not exact_term(text, term), f"{where}: names the private source term {term!r}: {text[:60]!r}")


def unit_lesson(course, unit):
    """The unit's lesson, with its dialogue (from the course's dialogues file) where it has one."""
    lesson = json.loads(unit["lesson"].read_text(encoding="utf-8-sig"))
    talk = course.get("dialogues", {}).get(unit["id"])
    if talk:
        lesson["dialogue"] = talk
    return lesson


def dialogue_notes(course):
    """Per dialogue: its size and what it uses of the unit, and with the story what the two use together."""
    notes = []
    for unit in course["units"]:
        lesson = unit_lesson(course, unit)
        talk = lesson.get("dialogue")
        if not talk:
            continue
        said = {use["card"] for line in talk["lines"] for use in line.get("uses", [])}
        told = {use["card"] for p in (lesson.get("story") or {}).get("paragraphs", []) for use in p.get("uses", [])}
        words = sum(len(re.findall(r"\w+", line["de"])) for line in talk["lines"])
        parts = []
        for section, name in (("vocabulary", "words"), ("grammar", "grammar"), ("redemittel", "phrases")):
            ids = [rec["id"] for rec in lesson[section]]
            parts.append(f"{name} {sum(i in said for i in ids)}/{len(ids)} (with the story {sum(i in said | told for i in ids)})")
        notes.append(f"{unit['id']}: {len(talk['lines'])} lines, {words} words; " + ", ".join(parts))
    return notes


def unit_narration(course, uid):
    """The unit's grammar narration with each point's extra examples ("more") added: what the plan and the app read."""
    told = {gid: ({"en": text} if isinstance(text, str) else dict(text)) for gid, text in course["narration"].get(uid, {}).items()}
    for gid, items in course["more_examples"].get(uid, {}).items():
        told.setdefault(gid, {})["more"] = items
    return told


def exact_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I) is not None


def unit_plan(lesson, voices, narration=None, announcement=None, translations=None):
    """Full listening order (episodes) plus what the app needs: German controls, grammar explanations,
    sections, the story's sentences per paragraph, the English example clips and those of every translation language."""
    clips, plan = lesson_plan(lesson, voices, narration, translations)

    def add(text):
        clip = speech.make_clip(text, "de", voices)
        clips.setdefault(clip.clip_id, clip)
        return clip.clip_id

    if announcement:
        plan["intro"] = add(announcement)            # opens the unit's listening episode
        plan["intro_examples"] = add(announcement + " Beispiele.")
    return clips, plan


def balanced_marks(text):
    """«…» open and close in turn, never nested."""
    depth = 0
    for char in text:
        if char in "«»":
            depth += 1 if char == "«" else -1
            if depth not in (0, 1):
                return False
    return depth == 0


def narration_notes(course):
    """Spoken explanations are keyed by unit id and grammar id; a typo would silently fall back, so refuse it.
    An explanation is a text (English), or {"de": in the course's language, "en": the English backup, "title" and
    "patterns" in the course's language for the written card}; the texts are written in blocks (explanation_blocks)."""
    lessons = {u["id"]: json.loads(u["lesson"].read_text(encoding="utf-8-sig")) for u in course["units"]}
    notes, name = [], course["profile"]["name"]
    for uid, points in course["narration"].items():
        require(uid in lessons, f"narration names an unknown unit: {uid}")
        grammar = {record["id"] for record in lessons[uid]["grammar"]}
        for gid, told in points.items():
            require(gid in grammar, f"narration names an unknown grammar point: {uid} {gid}")
            told, where = ({"en": told} if isinstance(told, str) else told), f"narration {uid} {gid}"
            require(isinstance(told, dict) and set(told) <= {"de", "en", "title", "patterns"} and (told.get("de") or told.get("en"))
                    and all(isinstance(told[key], str) and told[key].strip() for key in ("de", "en", "title") if key in told),
                    f'{where}: a text, or {{"de": the explanation in the language, "en": in English, "title", "patterns"}}')
            patterns = told.get("patterns", [])
            require(isinstance(patterns, list) and all(isinstance(p, dict) and set(p) == {"label", "form"}
                                                       and all(isinstance(v, str) and v.strip() for v in p.values())
                                                       for p in patterns),
                    f'{where}: patterns are a list of {{"label", "form"}}')
            for key in ("de", "en"):
                require(balanced_marks(told.get(key, "")), f"{where}: «…» do not close in turn in {key!r}")
            english = told.get("en", "")
            notes += [f"{uid} {gid}: '{word}' looks {name} but is not marked «…»"
                      for word in speech.unmarked_german(explanation_speech(english, True))]
            notes += [f"{uid} {gid}: an English example line is not all «…», so part of it is read as English: {body[:40]}"
                      for kind, body in explanation_blocks(english)
                      if kind == "ex" and not (body.startswith("«") and body.endswith("»") and body.count("«") == 1)]
    return notes


def build_course_plan(course):
    all_clips, units = {}, {}
    for unit in course["units"]:
        lesson = unit_lesson(course, unit)
        clips, plan = unit_plan(lesson, course["voices"], unit_narration(course, unit["id"]),
                                f"{course['title']}. {unit['label']}.", unit_translations(course, unit["id"]))
        all_clips.update(clips)
        units[unit["id"]] = plan
    plan = {"voices": course["voices"], "units": units, "texts": {cid: clip.text for cid, clip in all_clips.items()}}
    course["cache"].mkdir(parents=True, exist_ok=True)
    (course["cache"] / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return all_clips, plan


def missing(course, clips):
    folder = course["cache"] / "clips"
    return [cid for cid in clips if not (folder / f"{cid}.mp3").is_file()]


ffmpeg_exe = speech.ffmpeg_exe


def silence(course, seconds, ff):
    steps = max(1, min(25, round(seconds / STEP)))
    path = course["cache"] / "silence" / f"s{steps:02d}.mp3"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                        "-t", f"{steps * STEP:.1f}", "-c:a", "libmp3lame", "-b:a", "48k", "-ar", "24000", "-ac", "1",
                        "-write_xing", "0", str(path)], check=True)
    return path


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*!„“]', "", name).strip()


def lesson_steps(unit_plan_):
    """(clip, pause after it) in the sheet's listening order. German items get a pause about as long as the clip,
    to repeat them aloud; the story at the end is read straight through, with a breath after each paragraph."""
    grammar_titles = {cid for gid, chain in unit_plan_["explain"].items() for cid in chain[:1]}
    repeat = {cid: (0.8 if key.endswith("-head") else 1.0) for key, cid in unit_plan_["controls"].items()
              if cid not in grammar_titles and not key.startswith("story-")}
    story_gap = {cid: (1.1 if index == len(paragraph) - 1 else 0.35)
                 for paragraph in unit_plan_["story"] for index, cid in enumerate(paragraph)}
    if "story-title" in unit_plan_["controls"]:
        story_gap[unit_plan_["controls"]["story-title"]] = 0.9
    sections = set(unit_plan_["sections"].values())
    steps = [(unit_plan_["intro"], 0.8)]
    for cid in unit_plan_["sequence"]:
        steps.append((cid, ("section", 1.2) if cid in sections else ("story", story_gap[cid]) if cid in story_gap
                      else ("repeat", repeat[cid]) if cid in repeat else ("plain", 0.4)))
    return steps


def example_steps(unit_plan_, lesson, times):
    """Only the examples: each German sentence `times` times with a pause to repeat it, then its English meaning."""
    steps = [(unit_plan_["intro_examples"], 1.2)]
    for section in ("vocabulary", "grammar", "redemittel"):
        for record in lesson[section]:
            for index in range(len(record["examples"])):
                key = f'{record["id"]}-ex-{index}'
                steps += [(unit_plan_["controls"][key], ("repeat", 1.0))] * times
                steps.append((unit_plan_["english"][key], ("plain", 1.0)))
    return steps


def build_episodes(course, plan, kind="lesson", times=2):
    """One MP3 per unit: the whole sheet (kind 'lesson') or only its example sentences (kind 'examples')."""
    ff = ffmpeg_exe()
    examples = language.ui_table(course["profile"]).get("Beispiele", "Beispiele")       # German: Beispiele
    folder = course["episodes_dir"] / (examples if kind == "examples" else "")
    folder.mkdir(parents=True, exist_ok=True)
    clips_dir, total = course["cache"] / "clips", 0.0
    for number, unit in enumerate(course["units"], 1):
        unit_plan_ = plan["units"][unit["id"]]
        lesson = json.loads(unit["lesson"].read_text(encoding="utf-8-sig"))
        steps = lesson_steps(unit_plan_) if kind == "lesson" else example_steps(unit_plan_, lesson, times)
        parts, seconds = [], 0.0
        for cid, pause in steps:
            clip = clips_dir / f"{cid}.mp3"
            require(clip.is_file(), f"missing clip {cid}: run `course_audio.py synth` first")
            length = clip.stat().st_size / BYTES_PER_SECOND
            how, value = pause if isinstance(pause, tuple) else ("plain", pause)
            gap = 0.4 + length * value + 0.4 if how == "repeat" else value
            parts += [clip, silence(course, gap, ff)]
            seconds += length + max(STEP, round(gap / STEP) * STEP)
        listing = course["cache"] / "episodes" / f"{unit['id']}-{kind}.txt"
        listing.parent.mkdir(parents=True, exist_ok=True)
        listing.write_text("".join("file '" + p.as_posix().replace("'", "'\\''") + "'\n" for p in parts), encoding="utf-8")
        title = lesson["title"] if lesson["title"].startswith(unit["label"]) else f"{unit['label']} – {lesson['title']}"
        name = f"{number:02d} {title}" + (" – Beispiele" if kind == "examples" else "")
        album = f"{course['title']} – " + ("Beispiele" if kind == "examples" else "Hören und Nachsprechen")
        for term in course["private_terms"]:
            require(not exact_term(name + " " + album, term), f"episode name or album names the private source term {term!r}")
        target = folder / safe_name(f"{name}.mp3")
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", "-id3v2_version", "3", "-metadata", f"title={name[3:]}",
                        "-metadata", f"album={album}", "-metadata", f"artist={course['title']}",
                        "-metadata", f"track={number}/{len(course['units'])}", str(target)], check=True)
        total += seconds
        print(f"{target.name}: about {seconds / 60:.0f} min", flush=True)
    print(f"EPISODES ({kind}): {len(course['units'])} files, about {total / 3600:.1f} hours of listening")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("plan", "synth", "episodes"))
    parser.add_argument("--course", required=True, type=Path)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--kind", choices=("lesson", "examples"), default="lesson",
                        help="episodes: the whole sheet, or only the example sentences (into a Beispiele folder)")
    parser.add_argument("--repeat", type=int, default=2, help="episodes --kind examples: plays of each German sentence")
    parser.add_argument("--confirm-external-tts", action="store_true",
                        help="Confirm that the selected lesson text may be sent to the Edge TTS service")
    args = parser.parse_args(argv)
    try:
        course = load_course(args.course)
        notes = narration_notes(course)
        clips, plan = build_course_plan(course)
        todo = missing(course, clips)
        print(f"PLAN: {len(clips)} unique clips for {len(course['units'])} units; {len(todo)} not yet synthesized; "
              f"voices={course['voices']}; spoken grammar narration for "
              f"{sum(len(v) for v in course['narration'].values())} points; cache={course['cache']}")
        for note in notes:
            print("NARRATION: " + note)
        for note in dialogue_notes(course):
            print("DIALOGUE: " + note)
        if args.command == "plan":
            return 0
        require(args.confirm_external_tts, "Hosted synthesis sends lesson text externally; obtain approval and pass --confirm-external-tts")
        require(1 <= args.concurrency <= 8, "Concurrency must be from 1 to 8")
        if todo:
            asyncio.run(synthesize({cid: clips[cid] for cid in todo}, course["cache"], course["voices"], args.concurrency))
        seconds = sum((course["cache"] / "clips" / f"{cid}.mp3").stat().st_size for cid in clips) / BYTES_PER_SECOND
        print(f"SYNTH: all {len(clips)} clips cached, about {seconds / 60:.0f} minutes of speech")
        if args.command == "episodes":
            require(1 <= args.repeat <= 5, "--repeat must be from 1 to 5")
            build_episodes(course, plan, args.kind, args.repeat)
        return 0
    except (AudioError, speech.SpeechError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
