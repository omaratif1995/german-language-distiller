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
from embed_audio import AudioError, lesson_plan, require, synthesize  # noqa: E402
import language  # noqa: E402
import speech  # noqa: E402

BYTES_PER_SECOND = 6000   # edge-tts delivers 48 kbit/s constant-bitrate MP3
STEP = 0.4                # silence granularity in seconds
COURSE_KEYS = {"title", "subtitle", "narration", "voices", "cache", "episodes_dir", "new_per_day", "private_terms", "units"}


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
        seen.add(unit["id"])
        unit["lesson"] = (base / unit["lesson"]).resolve()
        unit["sheet"] = (base / unit["sheet"]).resolve()
        require(unit["lesson"].is_file(), f"lesson file not found: {unit['lesson']}")
        require(unit["sheet"].is_file(), f"sheet file not found: {unit['sheet']}")
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
    return course


def exact_term(text, term):
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I) is not None


def unit_plan(lesson, voices, narration=None, announcement=None):
    """Full listening order (episodes) plus what the app needs: German controls, grammar explanations,
    sections, the story's sentences per paragraph and the English example clips."""
    clips, plan = lesson_plan(lesson, voices, narration)

    def add(text):
        clip = speech.make_clip(text, "de", voices)
        clips.setdefault(clip.clip_id, clip)
        return clip.clip_id

    if announcement:
        plan["intro"] = add(announcement)            # opens the unit's listening episode
        plan["intro_examples"] = add(announcement + " Beispiele.")
    return clips, plan


def narration_notes(course):
    """Spoken explanations are keyed by unit id and grammar id; a typo would silently fall back, so refuse it."""
    lessons = {u["id"]: json.loads(u["lesson"].read_text(encoding="utf-8-sig")) for u in course["units"]}
    notes = []
    for uid, points in course["narration"].items():
        require(uid in lessons, f"narration names an unknown unit: {uid}")
        grammar = {record["id"] for record in lessons[uid]["grammar"]}
        for gid, told in points.items():
            require(gid in grammar, f"narration names an unknown grammar point: {uid} {gid}")
            told = {"en": told} if isinstance(told, str) else told
            require(isinstance(told, dict) and told and set(told) <= {"de", "en"}
                    and all(isinstance(text, str) and text.strip() for text in told.values()),
                    f"narration {uid} {gid}: a text, or {{\"de\": the explanation in the language, \"en\": in English}}")
            notes += [f"{uid} {gid}: '{word}' looks {course['profile']['name']} but is not marked «…»"
                      for word in speech.unmarked_german(told.get("en", ""))]
    return notes


def build_course_plan(course):
    all_clips, units = {}, {}
    for unit in course["units"]:
        lesson = json.loads(unit["lesson"].read_text(encoding="utf-8-sig"))
        clips, plan = unit_plan(lesson, course["voices"], course["narration"].get(unit["id"]),
                                f"{course['title']}. {unit['label']}.")
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
