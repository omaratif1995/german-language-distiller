#!/usr/bin/env python3
"""Build one offline study app from a course's reviewed sheets: Lernen, Üben and Spielen.

    build_course_app.py --course course.json --output Course_App_v1.html              # with audio from the cache
    build_course_app.py --course course.json --output Course_App_v1.html --no-audio   # study, practice and games only

Lernen: every reviewed sheet in course order, with its closing story. A 🔊 tap repeats a word or sentence (until
tapped again, or 1×/3×), a tap on a story sentence repeats that sentence, and a tap on an underlined story word shows
its meaning. "🎧 Anhören" opens a small panel: Ganze Lektion, Nur Beispiele or Geschichte, each German sentence played
1–5 times, once or endlessly; a bar at the bottom pauses, goes back and skips, and "▶ Weiter" goes on where a session
stopped. Üben: one card per sheet card, a small spaced-repetition schedule, one tap per card.
Spielen: five short games per unit made from the same cards (Hör-Bingo, Wortpaare, Satzbau, Der · Die · Das, Was sagt
man?).
Audio comes from `course_audio.py synth` and is embedded as base64 so the file works without a network.
See references/course-app.md.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import html
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_audio import (AUDIO_CSS, LISTEN_HTML, LISTEN_JS, AudioError, examples_order, explanation_sentences,  # noqa: E402
                         inject_example_buttons, inject_story_audio, listening_order, number_examples, play_button,
                         require, sentence_times, story_order, transform_card)
from course_audio import build_course_plan, exact_term, ffmpeg_exe, load_course  # noqa: E402
import language  # noqa: E402
import speech  # noqa: E402
import study_pack  # noqa: E402

KIND = {"voc": "w", "rule": "g", "phrase": "r"}


# ---------------------------------------------------------------- audio placement ---
def add_audio_buttons(page, lesson, unit_plan, used, prof=None, ui=None):
    """Target-language 🔊 buttons (headwords, examples, phrases, variants), a 🔊 Erklärung chain per grammar point
    (and an EN button for its English backup), and the story's sentence audio, paragraph buttons and word clips.
    `ui` translates the German labels."""
    controls, ui = unit_plan["controls"], ui or {}
    name = (prof or language.profile(lesson.get("target_language", "de")))["name"]

    def take(key):
        used.add(controls[key])
        return controls[key]

    for rec in lesson["vocabulary"]:
        def voc(block, rec=rec):
            head = take(f'{rec["id"]}-head')
            block, n = re.subn(r'(<div class="top"><span class="de">.*?</span>)(?=<span class="en">)',
                               lambda m: m.group(1) + play_button(head, f"Play {name} headword"), block, count=1, flags=re.S)
            require(n == 1, f"cannot place headword audio for {rec['id']}")
            return inject_example_buttons(block, [take(f'{rec["id"]}-ex-{i}') for i in range(len(rec["examples"]))], rec["id"])
        page = transform_card(page, "voc", rec["id"], voc)

    for rec in lesson["grammar"]:
        def rule(block, rec=rec):
            chain = unit_plan["explain"][rec["id"]]            # the spoken explanation (embedded at the explain bitrate)
            backup = unit_plan.get("explain_en", {}).get(rec["id"])
            button = (f'<button type="button" class="explain-button" data-chain="{" ".join(chain)}" '
                      f'aria-label="Listen to the explanation">{html.escape(ui.get("🔊 Erklärung", "🔊 Erklärung"))}</button>')
            if backup:                                         # the same explanation in English, one tap away
                button += (f'<button type="button" class="explain-button explain-en" data-chain="{" ".join(backup)}" '
                           f'aria-label="Listen to the explanation in English" title="English">EN</button>')
            block, n = re.subn(r"</h3>", lambda m: button + "</h3>", block, count=1)
            require(n == 1, f"cannot place explanation audio for {rec['id']}")
            return inject_example_buttons(block, [take(f'{rec["id"]}-ex-{i}') for i in range(len(rec["examples"]))], rec["id"])
        page = transform_card(page, "rule", rec["id"], rule)

    for rec in lesson["redemittel"]:
        def phrase(block, rec=rec):
            head = take(f'{rec["id"]}-head')
            block, n = re.subn(r'(<div class="head">.*?)(</div>)',
                               lambda m: m.group(1) + play_button(head, f"Play {name} expression") + m.group(2), block, count=1, flags=re.S)
            require(n == 1, f"cannot place expression audio for {rec['id']}")
            variants = iter([take(f'{rec["id"]}-variant-{i}') for i in range(len(rec.get("variants", [])))])
            block = re.sub(r'(<p class="variant">.*?)(</p>)',
                           lambda m: m.group(1) + play_button(next(variants), f"Play {name} variant") + m.group(2), block, flags=re.S)
            return inject_example_buttons(block, [take(f'{rec["id"]}-ex-{i}') for i in range(len(rec["examples"]))], rec["id"])
        page = transform_card(page, "phrase", rec["id"], phrase)

    if lesson.get("story"):
        used.update(cid for paragraph in unit_plan["story"] for cid in paragraph)
        used.add(controls["story-title"])
        heads = {rec["id"]: controls[f'{rec["id"]}-head'] for rec in lesson["vocabulary"] + lesson["redemittel"]}
        page = inject_story_audio(page, unit_plan, heads, ui)
    return page


def explanation_html(text, lang, prof, clip="", cache=None):
    """One written explanation: a <p> per paragraph, one box for a run of examples, a careful note marked ⚠, and
    every sentence a span. With the clip's word timings, each span knows when it is spoken (data-at, seconds)."""
    prof = prof or language.profile("de")
    blocks = explanation_sentences(text, prof)
    words = speech.clip_timings(cache, clip) if clip and cache else []
    times = iter(sentence_times([s for _, group in blocks for s in group], words) if words else [])

    def sentence(text, example):
        shown = html.escape(text)
        if example:                                   # the box already says it is the language's own
            shown = shown.replace("«", "").replace("»", "")
        else:                                         # a form or a word in bold, a longer piece like an example
            shown = re.sub(r"«(.+?)»", lambda m: f'<em class="{"x" if language.word_count(prof, m.group(1)) > 2 else "g"}">'
                                                 f'{m.group(1)}</em>', shown)
        at = next(times, None)
        stamp = "" if at is None else f' data-at="{at:.2f}"'
        return f'<span class="sn"{stamp}>{shown}</span>'

    parts, examples = [], []
    for kind, group in blocks + [("end", [])]:
        if kind != "ex" and examples:
            parts.append(f'<div class="say-ex">{"".join(examples)}</div>')
            examples = []
        if kind == "ex":
            examples.append("<p>" + " ".join(sentence(s, True) for s in group) + "</p>")
        elif kind != "end":
            parts.append(f'<p class="say-{kind}">' + " ".join(sentence(s, False) for s in group) + "</p>")
    source = f' data-clip="{clip}"' if clip else ""        # the clip whose playback lights it up
    return f'<div class="say" lang="{html.escape(lang)}"{source}>{"".join(parts)}</div>'


def write_explanations(page, lesson, narration, unit_plan=None, cache=None, prof=None, ui=None):
    """A grammar card whose narration speaks the course's language shows it written out, in place of the short
    English meaning, rule and contrast: the narration's blocks, its own title and patterns when it gives them, and
    the English backup folded away («Auf Englisch»). With audio, the sentence being read lights up."""
    prof, ui = prof or language.profile(lesson.get("target_language", "de")), ui or {}
    english = language.profile("de")                  # English sentences start like German ones, with a capital
    for rec in lesson["grammar"]:
        told = (narration or {}).get(rec["id"])
        if not isinstance(told, dict) or not told.get("de"):
            continue
        clips = {lang: ((unit_plan or {}).get(key, {}).get(rec["id"]) or [""])[0]
                 for lang, key in (("de", "explain"), ("en", "explain_en"))}

        def card(block, rec=rec, told=told, clips=clips):
            say = explanation_html(told["de"], prof["code"], prof, clips["de"], cache)
            if told.get("en"):
                say += (f'<details class="say-en"><summary>{html.escape(ui.get("Auf Englisch", "Auf Englisch"))}</summary>'
                        f'{explanation_html(told["en"], "en", english, clips["en"], cache)}</details>')
            block, n = re.subn(r"<p><b>Meaning:</b>.*?</p><p><b>Rule:</b>.*?</p>", lambda m: say, block, count=1, flags=re.S)
            require(n == 1, f"cannot place the written explanation for {rec['id']}")
            block = re.sub(r'<p class="contrast">.*?</p>', "", block, count=1, flags=re.S)
            if told.get("title"):
                block = re.sub(r"<h3>.*?</h3>", lambda m: f"<h3>{html.escape(told['title'])}</h3>", block, count=1, flags=re.S)
            if told.get("patterns"):
                rows = "".join(f'<p><b>{html.escape(p["label"])}:</b> {html.escape(p["form"])}</p>' for p in told["patterns"])
                block = re.sub(r'<div class="patterns">.*?</div>', lambda m: f'<div class="patterns">{rows}</div>', block,
                               count=1, flags=re.S)
            return block
        page = transform_card(page, "rule", rec["id"], card)
    return page


def accepted_articles(record, prof=None):
    """Every article the article game accepts: in German an adjective noun takes two (der/die Bekannte, as «ein
    Bekannter» in the forms shows), and in any language a noun whose forms name two articles (der or das Joghurt)."""
    prof = prof or language.profile("de")
    article, lemma, forms = record.get("article", ""), re.escape(record["lemma"]), record.get("forms", "")
    found, names = ({article} if article else set()), "|".join(map(re.escape, prof["articles"]))
    if article and prof.get("adjective_nouns") and re.search(rf"\beine? {lemma}r\b", forms):
        found |= {"der", "die"}
    for pair in re.finditer(rf"\b({names})\s*(?:/|\bor\b|\boder\b)\s*({names}) {lemma}\b", forms) if names else ():
        found |= set(pair.groups())
    return [a for a in prof["articles"] if a in found]


def word_forms(record, lesson, small=frozenset(), prof=None):
    """The forms a vocabulary card can take in a sentence: its lemma and every form the lesson marks for it,
    without the small words around them (`small`, from the language profile: sich, an, hat …). A language without
    spaces keeps each form whole (市場, 料理する)."""
    prof = prof or language.profile("de")
    texts = [record["lemma"]] + [target for example in record["examples"] for target in example.get("targets", [])]
    texts += [use["form"] for paragraph in (lesson.get("story") or {}).get("paragraphs", [])
              for use in paragraph.get("uses", []) if use["card"] == record["id"]]
    if not language.spaced(prof):
        return {text.casefold().strip() for text in texts if text.strip() and text.casefold().strip() not in small}
    return {token for text in texts for token in language.words(prof, text) if len(token) > 2 and token not in small}


def mentions(sentence, forms, endings=("en", "rn", "ln"), prof=None):
    """Whether a sentence contains one of the forms, or a near form of a long one (erinnern: erinnert, erinnerte;
    `endings` are the language's verb endings). Where words have no spaces between them (Japanese) or take small
    words in front (Arabic و، ب، ال: `inside_words`), a form counts anywhere in the sentence, a verb also by its stem
    (飲む: 飲みます); counting a word too often only leaves a sentence out of Hör-Bingo."""
    prof = prof or language.profile("de")
    text = sentence.casefold()
    if not language.spaced(prof) or prof["bingo"].get("inside_words"):
        stems = {form[:-len(end)] for form in forms for end in endings if form.endswith(end) and len(form) > len(end)}
        return any(form in text for form in set(forms) | stems)
    tokens = language.words(prof, text)
    for form in forms:
        stem = form[:-2] if len(form) >= 7 and form.endswith(tuple(endings)) else None
        if any(token == form or (stem and token.startswith(stem) and len(token) <= len(form) + 2) for token in tokens):
            return True
    return False


def puzzle_sentence(text, prof=None):
    """A sentence for Satzbau: 5 to 9 words and one plain sentence (no quotes, colons, brackets or dashes), so the
    words have one clear order and nothing but words is left to place. Without spaces the app finds the words
    (Intl.Segmenter) and keeps sentences of 5 to 9; here only the length and the marks are checked."""
    if re.search(r'[„“"«»…:;/()\[\]「」『』（）：；]| – ', text):
        return False
    if prof and not language.spaced(prof):
        return 4 <= len(text.strip()) <= 40
    return 5 <= len(text.split()) <= 9


def game_data(lesson, unit_plan=None):
    """What the games need, straight from the reviewed lesson data: words, phrases and sentences with their audio.

    Every vocabulary example lists the other words of the unit it contains ("m"), so Hör-Bingo calls a sentence only
    when its answer is clear, and still accepts any word of the card that the sentence really contains."""
    controls = unit_plan["controls"] if unit_plan else {}
    prof = language.profile(lesson.get("target_language", "de"))
    small, endings = set(prof["bingo"]["function_words"].split()), prof["bingo"]["verb_endings"]
    vocabulary = lesson["vocabulary"]
    forms = [word_forms(rec, lesson, small, prof) for rec in vocabulary]

    def js(text, at):                                 # a position as JavaScript counts it (UTF-16: 𠮟 is two)
        return len(text[:at].encode("utf-16-le")) // 2

    def example(record, index):
        item = record["examples"][index]
        return {"de": item["de"], "en": item["en"], "au": controls.get(f'{record["id"]}-ex-{index}', ""),
                "t": [[js(item["de"], a), js(item["de"], b)] for a, b in study_pack.target_spans(item, record["id"])]}

    def word(position, rec):
        examples = [dict(example(rec, index), m=[other for other, found in enumerate(forms)
                                                 if other != position and mentions(item["de"], found, endings, prof)])
                    for index, item in enumerate(rec["examples"])]
        entry = {"a": rec.get("article", ""), "w": rec["lemma"], "g": rec["gloss"], "h": controls.get(f'{rec["id"]}-head', ""),
                 "x": examples}
        both = accepted_articles(rec, prof)
        if len(both) > 1:
            entry["aa"] = both
        return entry

    return {
        "v": [word(position, rec) for position, rec in enumerate(vocabulary)],
        "r": [{"f": rec["frame"], "g": rec["gloss"], "w": rec["when"], "reg": rec.get("register", ""), "grp": rec["group"],
               "au": controls.get(f'{rec["id"]}-head', ""), "x": example(rec, 0)} for rec in lesson["redemittel"]],
        "s": [example(rec, index) for section in ("vocabulary", "grammar", "redemittel")
              for rec in lesson[section] for index, item in enumerate(rec["examples"]) if puzzle_sentence(item["de"], prof)]}


def compressed(cache, clip_id, bitrate, ff):
    src = cache / "clips" / f"{clip_id}.mp3"
    dst = cache / "app" / bitrate / f"{clip_id}.mp3"
    if not dst.exists():
        require(src.is_file(), f"missing clip {clip_id}: run `course_audio.py synth` first")
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "22050",
                        "-c:a", "libmp3lame", "-b:a", bitrate, str(dst)], check=True)
    return base64.b64encode(dst.read_bytes()).decode("ascii")


# ---------------------------------------------------------------- page assets ---
APP_CSS = r"""
  [hidden]{display:none !important}
  .bar{position:sticky;top:0;z-index:5;margin:-24px -16px 18px;padding:10px 16px;background:rgba(23,25,31,.95);
       backdrop-filter:blur(8px);border-bottom:1px solid var(--line);display:none;gap:8px;flex-wrap:wrap;align-items:center}
  .js .bar{display:flex}
  @media(max-width:520px){.bar{margin:-14px -9px 14px;padding:10px 9px}}
  .bar select,.bar input,.bar button,.pr select,.pr button{font:inherit;font-size:15px;color:var(--ink);background:var(--card);
       border:1px solid var(--line);border-radius:10px;padding:8px 10px;min-height:42px}
  .tabs{display:flex;gap:6px;flex-basis:100%}
  .tabs button{flex:1;font-weight:700;cursor:pointer}
  .tabs button[aria-pressed="true"],.pr .chips button[aria-pressed="true"]{background:var(--accent);color:#1a1030;border-color:var(--accent)}
  .bar select{flex:1 1 200px;min-width:0}
  .bar input{flex:1 1 160px;min-width:0}
  .bar .nav{width:44px;cursor:pointer}
  .bar .hits{flex-basis:100%;font-size:13px;color:var(--muted);display:none}
  .searching .bar .hits{display:block}
  .cover{text-align:center;margin:8px 0 22px;color:var(--muted);font-size:14px}
  .cover b{display:block;color:var(--ink);font-size:20px;margin-bottom:2px}
  .js .unit{display:none}
  .js .unit.on{display:block}
  .searching .unit{display:block}
  .searching article.miss,.searching .unit.empty{display:none !important}
  .searching h2,.searching .rule-under,.searching .unit > h3.miss{display:none}
  section.unit + section.unit{margin-top:40px}
  .explain-button{border:1px solid rgba(255,255,255,.28);color:#fff;background:rgba(15,23,42,.55);font:inherit;font-size:13px;
       font-weight:700;border-radius:999px;padding:4px 10px;margin-left:8px;cursor:pointer;white-space:nowrap}
  .explain-button.is-playing{background:#0f766e;border-color:#6ee7b7}
  .explain-en{margin-left:5px;padding:4px 8px;font-size:12px;letter-spacing:.04em;opacity:.85}
  .say{margin:4px 0 10px}
  .say p{margin:0 0 8px;font-size:15px;line-height:1.6}
  .say .say-ex{margin:0 0 8px;padding:5px 10px;background:var(--ex-bg);border-left:3px solid var(--ex-bar);border-radius:7px;
       color:var(--ex-ink);font-style:italic}
  .say .say-ex p{margin:2px 0}
  .say .say-warn{padding:5px 10px;background:rgba(242,211,107,.07);border-left:3px solid var(--yellow);border-radius:7px}
  .say .say-warn::before{content:"⚠ ";color:var(--yellow)}
  .say em{font-style:normal}
  .say em.g{font-weight:700;color:#f5e6b3}
  .say em.x{font-style:italic;color:#a9d6e0}
  .say .sn{border-radius:5px;padding:1px 0;transition:background .25s,color .25s;-webkit-box-decoration-break:clone;box-decoration-break:clone}
  .say .sn.lit{background:rgba(242,211,107,.22);color:#fff}
  details.say-en{margin:0 0 10px;padding-top:6px;border-top:1px solid var(--line)}
  details.say-en summary{cursor:pointer;color:var(--muted);font-size:13.5px;padding:2px 0}
  details.say-en .say{margin-bottom:2px}
  details.say-en .say p{font-size:14.5px}
  .mode-practice .lernen,.mode-games .lernen{display:none}
  #practice,#games{display:none}
  .mode-practice #practice,.mode-games #games{display:block}
  .mode-practice .lern-only,.mode-games .search-only{display:none !important}
  .mode-practice .now{bottom:calc(150px + env(safe-area-inset-bottom))}
  .tr-top{display:flex;align-items:center;gap:10px;margin:2px 0 12px}
  .tr-bar{flex:1;height:8px;border-radius:99px;background:var(--card);border:1px solid var(--line);overflow:hidden}
  .tr-bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),#34d399);transition:width .35s ease}
  .tr-count{font-size:14px;color:var(--muted);white-space:nowrap}
  .tr-streak{font-size:14px;white-space:nowrap}
  .fc{position:relative;background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 18px;min-height:250px;
      box-shadow:0 10px 28px rgba(0,0,0,.3);overflow-wrap:anywhere;touch-action:pan-y;user-select:none;-webkit-user-select:none;
      transition:transform .22s ease,opacity .22s ease,border-color .15s}
  .fc.dragging{transition:none}
  .fc.hint-good{border-color:#34d399}
  .fc.hint-again{border-color:#f87171}
  .fc.fly-right{transform:translateX(120%) rotate(12deg);opacity:0}
  .fc.fly-left{transform:translateX(-120%) rotate(-12deg);opacity:0}
  .fc .tag{font-size:12px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:12px}
  .fc .front{font-size:26px;font-weight:700;line-height:1.3}
  .fc .front .q-mean{display:block}
  .fc .front .q-when{display:block;font-size:15px;font-weight:400;color:var(--muted);margin-top:10px}
  .fc .peek{margin-top:28px;font-size:13px;color:var(--muted);text-align:center}
  .fc.enter{animation:enter .22s ease}
  @keyframes enter{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
  .fc .back{margin-top:16px;border-top:1px dashed var(--line);padding-top:12px;animation:reveal .25s ease}
  .fc .back article{background:none;border:0;box-shadow:none;padding:0;margin:0}
  .fc .msg{text-align:center;padding:26px 4px}
  .fc .msg .big{font-size:40px;line-height:1.1;margin-bottom:8px}
  .fc .msg h3{margin:0 0 6px;font-size:22px}
  .fc .msg p{margin:4px 0;color:var(--muted)}
  @keyframes reveal{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
  body{background-repeat:no-repeat}
  .dock{position:sticky;bottom:0;z-index:4;margin:0 -16px;padding:12px 16px env(safe-area-inset-bottom);
        background:linear-gradient(rgba(23,25,31,0),var(--bg) 12px)}
  @media(max-width:520px){.dock{margin:0 -9px;padding-left:9px;padding-right:9px}}
  .acts{display:flex;gap:10px}
  .acts button{flex:1;min-height:56px;font-size:17px;font-weight:700;border-radius:14px;cursor:pointer}
  .acts .main{background:var(--accent);color:#1a1030;border-color:var(--accent)}
  .acts .again{background:#5b2333;border-color:#9f3a55;color:#ffe4ea}
  .acts .good{background:#145c4d;border-color:#34d399;color:#e7fff6}
  .undo{display:flex;align-items:center;justify-content:center;gap:10px;min-height:44px;font-size:14px;color:var(--muted);visibility:hidden}
  .undo.on{visibility:visible}
  .undo span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .pr .undo button{flex:none;min-height:32px;padding:3px 12px;font-size:13px;border-radius:999px;background:none;cursor:pointer}
  .settings{margin-top:24px;border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:rgba(36,39,46,.55)}
  .settings summary{cursor:pointer;color:var(--muted);font-size:14px;padding:4px 0}
  .settings[open] summary{margin-bottom:12px}
  .pr .group{margin:0 0 14px}
  .pr .lab{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
  .pr .chips{display:flex;flex-wrap:wrap;gap:6px}
  .pr .chips button{min-height:36px;padding:5px 10px;font-size:14px;cursor:pointer}
  .pr #s-units .chips + .chips{margin-top:10px}
  .pr .chips button.grp{font-weight:700;min-width:58px}
  .pr .chips button[aria-pressed="mixed"]{border-color:var(--accent);color:var(--accent)}
  .pr .stat{font-size:13px;color:var(--muted)}
  .pr .stat .line{display:block}
  .pr .backup{display:flex;gap:8px;flex-wrap:wrap}
  .pr .backup button,.pr .backup label{font:inherit;font-size:14px;cursor:pointer;color:var(--ink);background:var(--card);
       border:1px solid var(--line);border-radius:10px;padding:8px 10px;min-height:42px;box-sizing:border-box;display:inline-flex;align-items:center}
  .pr .backup input{display:none}
  /* ---- Spielen ---- */
  .g-menu{display:grid;gap:10px}
  .g-lead{color:var(--muted);font-size:14px;margin:2px 0 8px}
  .g-tile{display:grid;grid-template-columns:54px 1fr;column-gap:12px;align-items:center;text-align:left;padding:14px;border-radius:16px;cursor:pointer;
          background:var(--card);border:1px solid var(--line);color:var(--ink);font:inherit;transition:transform .12s,border-color .2s}
  .g-tile:hover{border-color:var(--accent)}
  .g-tile:active{transform:scale(.98)}
  .g-icon{grid-row:1 / span 3;font-size:36px;display:grid;place-items:center}
  .g-name{font-size:18px;font-weight:800}
  .g-desc{font-size:13.5px;color:var(--muted)}
  .g-best{font-size:13px;color:var(--yellow);margin-top:2px}
  .g-random{font:inherit;font-weight:800;font-size:16px;min-height:54px;border-radius:14px;cursor:pointer;background:var(--accent);color:#1a1030;border:0}
  .g-total{color:var(--yellow);font-size:14px;font-weight:700;margin:-2px 0 2px}
  .g-head{display:flex;align-items:center;gap:10px;margin:0 0 6px}
  .g-prog{display:flex;align-items:center;gap:10px;height:24px;margin:0 0 10px}
  .g-rail{flex:1;height:7px;border-radius:99px;background:var(--card);overflow:hidden}
  .g-rail i{display:block;height:100%;width:0;border-radius:99px;background:linear-gradient(90deg,var(--accent),#34d399);transition:width .35s ease}
  .g-clock i{width:100%;background:linear-gradient(90deg,#34d399,#f2d36b);transition:width 1s linear}
  .g-run{min-width:3.2em;text-align:right;font-weight:800;font-size:15px;color:#fdba74;white-space:nowrap}
  .g-run.bump{animation:bump .4s ease}
  .g-drill{color:#fdba74;font-weight:700;font-size:14px;margin:0 0 8px}
  .win{animation:win .45s ease}
  @keyframes win{40%{transform:scale(1.06)}}
  @keyframes bump{40%{transform:scale(1.35)}}
  .g-title{font-size:20px;font-weight:800;flex:1}
  .g-info{color:var(--muted);font-size:14px;white-space:nowrap}
  .g-close{font:inherit;width:42px;height:42px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
  .g-acts{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
  .g-acts button{flex:1;min-height:50px;font:inherit;font-weight:700;font-size:16px;border-radius:14px;cursor:pointer;background:var(--card);color:var(--ink);border:1px solid var(--line)}
  .g-acts .main{background:var(--accent);color:#1a1030;border-color:var(--accent)}
  .g-acts .g-retry{flex-basis:100%}
  .g-end{text-align:center;padding:16px 4px}
  .g-end p{margin:6px 0;color:var(--muted)}
  .g-big{font-size:58px;line-height:1.1}
  .g-stars{font-size:32px;color:var(--yellow);letter-spacing:5px;margin:4px 0 8px}
  .g-end .g-rec{color:#6ee7b7;font-weight:800}
  .g-ok{color:#6ee7b7;font-weight:800}
  .g-no{color:#fda4af;font-weight:800}
  .b-call{display:flex;align-items:center;gap:10px;min-height:66px;padding:12px 14px;border-radius:14px;background:var(--ex-bg);border-left:4px solid var(--ex-bar);margin-bottom:12px}
  .b-cue{flex:1;font-size:16.5px;line-height:1.45}
  .b-cue mark{font-weight:700}
  .b-ear{color:var(--muted)}
  .b-again{font:inherit;font-size:14px;border-radius:999px;padding:7px 12px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer;flex:none}
  .b-grid{display:grid;gap:8px}
  .b-cell{position:relative;min-height:76px;padding:8px;border-radius:14px;font:inherit;font-size:15.5px;font-weight:700;line-height:1.25;cursor:pointer;
          background:var(--card);color:var(--ink);border:2px solid var(--line);overflow-wrap:anywhere;transition:background .2s,border-color .2s}
  .b-cell.on{background:#145c4d;border-color:#34d399}
  .b-cell.on::after{content:'✓';position:absolute;top:4px;right:8px;color:#6ee7b7;font-size:15px}
  .b-cell.hint{animation:hint .6s ease 3}
  .b-none{width:100%;margin-top:10px;min-height:50px;font:inherit;font-weight:700;border-radius:14px;cursor:pointer;background:transparent;color:var(--ink);border:2px dashed var(--muted)}
  .b-fb{min-height:76px;margin-top:12px;font-size:14.5px;line-height:1.45}
  .b-tr{color:#7fb3d9;font-style:italic;margin-top:2px}
  .b-bingo{position:fixed;left:50%;top:42%;transform:translate(-50%,-50%) rotate(-6deg);font-size:64px;font-weight:900;color:#f2d36b;
           text-shadow:0 6px 24px rgba(0,0,0,.6);z-index:60;animation:pop .45s ease;pointer-events:none}
  .gap{display:inline-block;min-width:3em;border-bottom:2px solid var(--yellow);color:transparent}
  .s-prompt{font-size:17px;margin:4px 0 10px;font-style:italic;color:#c7d2fe}
  .s-line{min-height:60px;padding:10px;border-radius:14px;border:2px dashed var(--line);display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:17px}
  .s-word{background:var(--ex-bg);padding:5px 9px;border-radius:9px}
  .s-tiles{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
  .s-tile{font:inherit;font-size:17px;padding:9px 13px;border-radius:12px;cursor:pointer;background:var(--card);color:var(--ink);border:1px solid var(--line);min-height:48px}
  .s-tile.used{visibility:hidden}
  .s-tile.hint{border-color:var(--yellow);box-shadow:0 0 0 3px rgba(242,211,107,.35)}
  .s-fb{margin-top:10px;min-height:24px}
  .a-score{text-align:center;color:var(--muted);margin-bottom:8px;min-height:22px}
  .a-card{min-height:156px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;border-radius:18px;
          background:var(--card);border:2px solid var(--line);padding:16px;transition:border-color .15s}
  .a-card.good{border-color:#34d399}
  .a-card.bad{border-color:#f87171}
  .a-word{font-size:32px;font-weight:800;overflow-wrap:anywhere}
  .a-gloss{color:var(--muted);margin-top:6px}
  .a-btns{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}
  .a-btns button{min-height:68px;font:inherit;font-size:22px;font-weight:800;border-radius:16px;cursor:pointer;border:0;color:#10141c}
  .a-der{background:var(--der)} .a-die{background:var(--die)} .a-das{background:var(--das)}
  .r-sit{padding:14px;border-radius:14px;background:var(--ex-bg);border-left:4px solid var(--phrase-bar);font-size:17px;margin-bottom:12px}
  .r-reg{color:var(--muted);font-size:13px;margin-top:4px}
  .r-opts{display:grid;gap:8px}
  .r-opt{text-align:left;font:inherit;font-size:16px;padding:12px 14px;border-radius:14px;cursor:pointer;background:var(--card);color:#6ee7b7;border:2px solid var(--line);font-weight:700}
  .r-opt.ok{border-color:#34d399;background:#145c4d;color:#e7fff6}
  .r-opt.no{border-color:#f87171;background:#5b2333;color:#ffe4ea}
  .r-fb{margin-top:12px;font-size:14.5px;line-height:1.45}
  .p-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px}
  .p-col{display:grid;gap:8px;align-content:start}
  .p-card{min-height:62px;padding:8px 10px;border-radius:14px;font:inherit;font-size:15.5px;font-weight:700;line-height:1.25;cursor:pointer;
          background:var(--card);color:var(--ink);border:2px solid var(--line);overflow-wrap:anywhere}
  .p-en{font-weight:600;font-size:14.5px;color:#c7d2fe}
  .p-card.sel{border-color:var(--yellow);box-shadow:0 0 0 3px rgba(242,211,107,.3)}
  .p-card.done{opacity:.3;border-color:#34d399;cursor:default;transition:opacity .35s .3s}
  .shake{animation:shake .35s}
  @keyframes shake{20%,60%{transform:translateX(-6px)}40%,80%{transform:translateX(6px)}}
  @keyframes hint{50%{box-shadow:0 0 0 5px rgba(242,211,107,.45)}}
  @keyframes pop{from{transform:translate(-50%,-50%) scale(.4) rotate(-6deg)}}
  .confetti{position:fixed;inset:0;pointer-events:none;z-index:55;overflow:hidden}
  .confetti i{position:absolute;top:-14px;width:9px;height:14px;border-radius:2px;animation:fall linear forwards}
  @keyframes fall{to{transform:translateY(108vh) rotate(600deg)}}
  @media(prefers-reduced-motion:reduce){.fc,.fc.enter,.fc .back,.tr-bar i{transition:none;animation:none}.shake,.b-cell.hint,.b-bingo,.win,.g-run.bump{animation:none}}
"""

# A right-to-left language: cards, game words and the listening line take their direction from their first letter
# (as on the sheet, study_pack.RTL_CSS), and the words of Satzbau line up from the right.
RTL_APP_CSS = (".front,.q-mean,.q-when,.b-cue,.b-cell,.b-fb div,.s-word,.s-tile,.a-word,.r-opt,.r-fb div,.p-card,#now-t,.say p"
               "{unicode-bidi:plaintext}.r-opt{text-align:start}.s-line,.s-tiles{direction:rtl}")

APP_JS = r"""
(function(){
  'use strict';
  var d=document, root=d.documentElement; root.classList.add('js');
  var AU={}, IDX=__INDEX__, SEQ=__SEQUENCES__, EXS=__EXAMPLES__, STO=__STORIES__, CARDS=__CARDS__, ORDER=__ORDER__, CFG=__CONFIG__, G=__GAME__;
  var K=CFG.key, ARTS=CFG.arts||[], COL=CFG.col||{};                 /* the language's articles and their colours */
  function load(k,dflt){try{var v=localStorage.getItem(K+':'+k);return v?JSON.parse(v):dflt;}catch(e){return dflt;}}
  function save(k,v){try{localStorage.setItem(K+':'+k,JSON.stringify(v));}catch(e){}}
  var ui=load('ui',{}), state=load('srs',{}), meta=load('meta',{day:0,fresh:0,extra:0,streak:0,last:-9,done:0,good:0});
  function today(){var t=new Date();return Math.floor((t.getTime()-t.getTimezoneOffset()*60000)/86400000);}
  /* audio sits in per-unit text blocks after this script; a unit's clips are unpacked on first use, but only once the
     page has read the whole block (a block still being read would give half a clip), and the block's text then goes */
  function parsed(el){ return d.readyState!=='loading'||!!el.nextElementSibling; }
  function need(id){ if(AU[id]!==undefined) return AU[id]; var k=IDX[id], el=k===undefined?null:d.getElementById('au-'+k);
    if(el && !el.getAttribute('data-read') && parsed(el)){ el.textContent.split(';').forEach(function(p){ var i=p.indexOf(':'); if(i>0) AU[p.slice(0,i)]=p.slice(i+1); });
      el.setAttribute('data-read','1'); el.textContent=''; }
    return AU[id]||''; }
  /* kept once these clips can be read: a unit's sound works as soon as its block is in, not after the whole page */
  function whenAudio(ids){ return new Promise(function(ok){ (function check(){
    if(ids.every(function(id){ var k=IDX[id], el; return k===undefined||AU[id]!==undefined||!!((el=d.getElementById('au-'+k))&&parsed(el)); })) ok();
    else setTimeout(check,120); })(); }); }
__LISTEN__
  /* ---------------- Lernen: unit picker and search ---------------- */
  var units=[].slice.call(d.querySelectorAll('section.unit')), sel=d.getElementById('pick'), q=d.getElementById('q'), hits=d.getElementById('hits');
  function show(id,scroll){ if(!units.some(function(u){return u.id===id;})) id=units[0].id;
    units.forEach(function(u){u.classList.toggle('on',u.id===id);}); sel.value=id; ui.unit=id; save('ui',ui); if(scroll) window.scrollTo(0,0); }
  function stepUnit(n){ var i=units.findIndex(function(u){return u.id===sel.value;}); i=Math.max(0,Math.min(units.length-1,i+n)); stopAll(); show(units[i].id,true); unitChanged(); }
  function unitChanged(){ if(d.body.classList.contains('mode-games')) Games.open(); }
  sel.addEventListener('change',function(){stopAll(); show(sel.value,true); unitChanged();});
  d.getElementById('prev').addEventListener('click',function(){stepUnit(-1);});
  d.getElementById('next').addEventListener('click',function(){stepUnit(1);});
  function norm(s){return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/ß/g,'ss');}
  var arts=null, heads=null, tq;                  /* built on the first search, not while the app opens */
  function index(){ if(arts) return;
    arts=[].slice.call(d.querySelectorAll('section.unit article')).map(function(a){return [a,norm(a.textContent)];});
    heads=[].slice.call(d.querySelectorAll('section.unit > h3')).map(function(h){ var list=[], n=h.nextElementSibling;   /* a subheading and its cards */
      for(;n&&!/^H[23]$/.test(n.tagName);n=n.nextElementSibling) list=list.concat(n.tagName==='ARTICLE'?[n]:[].slice.call(n.querySelectorAll('article')));
      return [h,list]; }); }
  q.addEventListener('input',function(){clearTimeout(tq); tq=setTimeout(search,150);});
  function search(){ var v=norm(q.value.trim()); index();
    if(v.length<2){ d.body.classList.remove('searching'); arts.forEach(function(c){c[0].classList.remove('miss');}); heads.forEach(function(h){h[0].classList.remove('miss');});
      units.forEach(function(u){u.classList.remove('empty');}); return; }
    d.body.classList.add('searching'); var n=0;
    arts.forEach(function(c){var m=c[1].indexOf(v)>=0; c[0].classList.toggle('miss',!m); if(m) n++;});
    heads.forEach(function(h){ h[0].classList.toggle('miss',!h[1].some(function(a){ return !a.classList.contains('miss'); })); });   /* no empty subheadings */
    units.forEach(function(u){u.classList.toggle('empty',!u.querySelector('article:not(.miss)'));});
    hits.textContent=n+(n===1?' Karte':' Karten')+' gefunden'; }

  /* ---------------- tabs ---------------- */
  var tabs={l:d.getElementById('tab-l'),p:d.getElementById('tab-p'),g:d.getElementById('tab-g')};
  function mode(m){ stopAll(); Games.stop(); d.body.classList.toggle('mode-practice',m==='p'); d.body.classList.toggle('mode-games',m==='g');
    Object.keys(tabs).forEach(function(k){ tabs[k].setAttribute('aria-pressed',String(k===m)); });
    ui.tab=m; save('ui',ui); if(m==='p') start(); if(m==='g') Games.open(); window.scrollTo(0,0); }
  Object.keys(tabs).forEach(function(k){ tabs[k].addEventListener('click',function(){ mode(k); }); });

  /* ---------------- Üben: spaced repetition with rounds ---------------- */
  var DAYS=[0,1,3,7,14,30,60], KIND={w:'Wortschatz',g:'Grammatik',r:'Redemittel'};
  var S={units:ui.units||ORDER.slice(), kinds:ui.kinds||['w','g','r'], dir:ui.dir||'de', perDay:ui.perDay||CFG.perDay,
         auto:ui.auto!==false, round:(ui.round===undefined?10:ui.round), browse:!!ui.browse};
  var queue=[], cur=null, shown=false, missed=false, view='card', ses={inRound:0,rg:0,ra:0}, bList=[], bIdx=0;
  var busy=false, readyAt=0, undo=null, undoTimer=null;
  var fc=d.getElementById('fc'), acts=d.getElementById('acts'), undoBox=d.getElementById('undo');
  function persist(){ ui.units=S.units; ui.kinds=S.kinds; ui.dir=S.dir; ui.perDay=S.perDay; ui.auto=S.auto; ui.round=S.round; ui.browse=S.browse; save('ui',ui); }
  function pool(){ return CARDS.filter(function(c){return S.units.indexOf(c.u)>=0 && S.kinds.indexOf(c.k)>=0;}); }
  function newDay(){ var T=today(); if(meta.day!==T){ meta.day=T; meta.fresh=0; meta.extra=0; meta.done=0; meta.good=0; save('meta',meta); } }
  function start(){ newDay(); dropUndo(); renderSettings();
    if(S.browse){ bList=pool(); bIdx=Math.min(bIdx,Math.max(0,bList.length-1)); cur=bList[bIdx]||null; shown=false; missed=false; view=cur?'card':'empty'; render(); return; }
    var T=today(), p=pool();
    /* due cards come from every lesson, so choosing lessons never pauses what you already learn; new ones from the chosen */
    var due=CARDS.filter(function(c){var s=state[c.id]; return s && s[1]<=T && S.kinds.indexOf(c.k)>=0;}).sort(function(a,b){return state[a.id][1]-state[b.id][1]||state[a.id][0]-state[b.id][0];});
    var fresh=p.filter(function(c){return !state[c.id];}).slice(0,Math.max(0,S.perDay+meta.extra-meta.fresh));
    queue=[]; var i=0,j=0; while(i<due.length||j<fresh.length){ if(i<due.length) queue.push(due[i++]); if(i<due.length) queue.push(due[i++]); if(j<fresh.length) queue.push(fresh[j++]); }
    ses={inRound:0,rg:0,ra:0};
    if(!p.length&&!due.length){ cur=null; view='empty'; render(); return; }
    next(); }
  function next(){ stopAll(); cur=queue.shift()||null; shown=false; missed=false; view=cur?'card':'done'; readyAt=Date.now()+250;   /* a double tap must not grade the next card */
    fc.style.transition='none'; render(); void fc.offsetWidth; fc.style.transition=''; fc.classList.add('enter');
    if(cur) autoFront(); }
  function autoFront(){ if(S.auto && cur.k==='w' && S.dir==='de' && cur.fa) clip(cur.fa); }
  function autoBack(){ if(!S.auto) return; if(cur.k==='w' && S.dir==='en' && cur.fa) clip(cur.fa); else if(cur.k==='r' && cur.ba) clip(cur.ba); }
  function topbar(){ var t=d.getElementById('tr-count'), bar=d.getElementById('tr-fill'), st=d.getElementById('tr-streak');
    if(S.browse){ t.textContent=(bList.length?(bIdx+1)+' / '+bList.length:'0'); bar.style.width=(bList.length?100*(bIdx+1)/bList.length:0)+'%'; }
    else { var left=queue.length+(cur && view==='card'?1:0), all=(meta.done||0)+left; t.textContent='Heute '+(meta.done||0)+' / '+all; bar.style.width=(all?100*(meta.done||0)/all:0)+'%'; }
    st.textContent=meta.streak>0 && meta.last>=today()-1 ? '🔥 '+meta.streak : ''; }
  function msg(big,title,lines){ return '<div class="msg"><div class="big">'+big+'</div><h3>'+title+'</h3>'+lines.map(function(l){return '<p>'+l+'</p>';}).join('')+'</div>'; }
  function render(){ topbar(); fc.className='fc'; fc.style.transform='';
    if(view==='empty'){ fc.innerHTML=msg('🗂️','Keine Karten','<span>Wähle in den Einstellungen Lektionen und Teile.</span>'.split('|')); acts.innerHTML=''; return; }
    if(view==='done'){ var more=pool().some(function(c){return !state[c.id];});
      fc.innerHTML=msg('🎉','Fertig für heute!',[meta.done?meta.done+' Karten geübt · '+meta.good+' gewusst':'Heute ist nichts fällig.', meta.streak>1?'🔥 '+meta.streak+' Tage in Folge':'Bis morgen!']);
      acts.innerHTML=(more?'<button type="button" class="main" data-a="extra">+10 neue Karten</button>':'')+'<button type="button" data-a="browse">Durchblättern</button>'; return; }
    if(view==='round'){ fc.innerHTML=msg('💪','Runde geschafft!',['✓ '+ses.rg+' gewusst · ✗ '+ses.ra+' nochmal','Noch '+(queue.length+(cur?1:0))+' Karten für heute']);
      acts.innerHTML='<button type="button" class="main" data-a="resume">Weiter</button><button type="button" data-a="pause">Pause</button>'; return; }
    if(view==='paused'){ fc.innerHTML=msg('☕','Gute Pause!',['Dein Fortschritt ist gespeichert.']); acts.innerHTML='<button type="button" class="main" data-a="resume">Weiter lernen</button>'; return; }
    var reverse=(cur.k==='w' && S.dir==='en'), cls={w:'voc',g:'rule',r:'phrase'}[cur.k];
    fc.innerHTML='<div class="tag">'+cur.l+' · '+KIND[cur.k]+'</div><div class="front">'+(reverse?cur.r:cur.f)+'</div>'+
      (shown?'<div class="back"><article class="'+cls+'">'+cur.b+'</article></div>':'<div class="peek">Tippen = Antwort ansehen</div>');
    if(S.browse){ acts.innerHTML='<button type="button" data-a="prev" aria-label="Zurück">‹</button><button type="button" class="main" data-a="flip">'+(shown?'Verstecken':'Antwort zeigen')+'</button><button type="button" data-a="nxt" aria-label="Weiter">›</button>'; return; }
    acts.innerHTML=missed?'<button type="button" class="main" data-a="go">Weiter ›</button>'
      :'<button type="button" class="again" data-a="again">✗ Nochmal</button><button type="button" class="good" data-a="good">✓ Gewusst</button>'; }

  /* one tap per card: ✓ = known, next card (its answer stays below for a moment, with undo);
     ✗ = not known, the answer opens, then Weiter; a tap on the card only peeks */
  function peek(){ if(view!=='card'||!cur||missed) return; shown=!shown; render(); if(shown) autoBack(); }
  function canGrade(){ return !busy && view==='card' && !!cur && !missed && !S.browse && Date.now()>=readyAt; }
  function grade(ok){ var T=today(), s=state[cur.id], isNew=!s,
      snap={card:cur, s:s?s.slice():null, meta:JSON.stringify(meta), ses:JSON.stringify(ses), queue:queue.slice()};
    if(isNew){ meta.fresh++; }
    if(meta.last!==T){ meta.streak=(meta.last===T-1?meta.streak:0)+1; meta.last=T; }
    if(ok){ var box=isNew?2:Math.min((s[0]||0)+1,6); state[cur.id]=[box,T+DAYS[box]]; meta.good=(meta.good||0)+1; ses.rg++; }
    else { state[cur.id]=[0,T]; ses.ra++; queue.splice(Math.min(3,queue.length),0,cur); }
    meta.done=(meta.done||0)+1; ses.inRound++; save('srs',state); save('meta',meta); if(navigator.vibrate) navigator.vibrate(12);
    return snap; }
  function advance(){ if(S.round && ses.inRound>=S.round && queue.length){ ses.inRound=0; cur=null; view='round'; render(); ses.rg=0; ses.ra=0; return; }
    next(); }
  function fly(dir,then){ if(busy) return; busy=true; fc.style.transform=''; fc.classList.add(dir);
    setTimeout(function(){ busy=false; then(); },200); }
  function good(){ if(!canGrade()) return; var quick=!shown;
    fly('fly-right',function(){ var snap=grade(true); if(quick) offerUndo(snap); else dropUndo(); advance(); }); }
  function again(){ if(!canGrade()) return; dropUndo();
    if(shown){ fly('fly-left',function(){ grade(false); advance(); }); return; }
    grade(false); missed=true; shown=true; render(); autoBack(); }
  function offerUndo(snap){ clearTimeout(undoTimer); undo=snap; undoBox.innerHTML='';
    var t=d.createElement('span'); t.textContent='✓ '+(snap.card.a||''); undoBox.appendChild(t);
    var b=d.createElement('button'); b.type='button'; b.textContent='Rückgängig'; b.addEventListener('click',doUndo); undoBox.appendChild(b);
    undoBox.classList.add('on'); undoTimer=setTimeout(dropUndo,6000); }
  function dropUndo(){ clearTimeout(undoTimer); undo=null; if(undoBox) undoBox.classList.remove('on'); }
  function doUndo(){ if(!undo) return; var u=undo; dropUndo(); stopAll();
    if(u.s) state[u.card.id]=u.s; else delete state[u.card.id];
    meta=JSON.parse(u.meta); ses=JSON.parse(u.ses); queue=u.queue; cur=u.card; shown=true; missed=false; view='card';
    save('srs',state); save('meta',meta); render(); autoBack(); }
  function browseMove(n){ bIdx=Math.max(0,Math.min(bList.length-1,bIdx+n)); cur=bList[bIdx]; shown=false; stopAll(); render(); }
  acts.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; var a=b.getAttribute('data-a');
    if(a==='good') good(); else if(a==='again') again(); else if(a==='go') advance(); else if(a==='flip') peek();
    else if(a==='resume'){ next(); } else if(a==='pause'){ dropUndo(); view='paused'; render(); }
    else if(a==='extra'){ meta.extra+=10; save('meta',meta); start(); }
    else if(a==='browse'){ S.browse=true; persist(); start(); }
    else if(a==='prev') browseMove(-1); else if(a==='nxt') browseMove(1); });
  /* tap = peek, swipe right = ✓, swipe left = ✗; after ✗ a swipe either way = Weiter */
  var sx=0, sy=0, dx=0, dragging=false;
  fc.addEventListener('pointerdown',function(e){ if(e.target.closest('button,details')||view!=='card') return; dragging=true; sx=e.clientX; sy=e.clientY; dx=0; fc.classList.add('dragging');
    try{ fc.setPointerCapture(e.pointerId); }catch(err){} });   /* a mouse swipe may leave the window */
  fc.addEventListener('pointermove',function(e){ if(!dragging) return; dx=e.clientX-sx; var dy=e.clientY-sy;
    if(!S.browse && Math.abs(dx)>Math.abs(dy)){ fc.style.transform='translateX('+dx+'px) rotate('+(dx/28)+'deg)';
      if(!missed){ fc.classList.toggle('hint-good',dx>40); fc.classList.toggle('hint-again',dx<-40); } } });
  function end(e){ if(!dragging) return; dragging=false; fc.classList.remove('dragging'); var dy=(e&&e.clientY!==undefined)?e.clientY-sy:0;
    if(!S.browse && Math.abs(dx)>80){
      if(missed && !busy){ fly(dx>0?'fly-right':'fly-left',advance); return; }
      if(canGrade()){ if(dx>0) good(); else again(); return; } }
    fc.style.transform=''; fc.classList.remove('hint-good','hint-again');
    if(Math.abs(dx)<10 && Math.abs(dy)<10) peek(); }
  fc.addEventListener('pointerup',end); fc.addEventListener('pointercancel',function(){ dragging=false; fc.classList.remove('dragging','hint-good','hint-again'); fc.style.transform=''; });
  d.addEventListener('keydown',function(e){ if(!d.body.classList.contains('mode-practice')||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)||e.repeat||e.ctrlKey||e.metaKey||e.altKey) return;
    var k=e.key, onButton=!!(e.target.closest && e.target.closest('button,summary')), confirm=(k===' '||k==='Enter') && !onButton;
    if((k==='Backspace'||k==='z'||k==='Z') && undo){ e.preventDefault(); doUndo(); return; }
    if(view==='round'||view==='paused'){ if(confirm){ e.preventDefault(); next(); } return; }
    if(view!=='card') return;
    if(S.browse){ if(k==='ArrowRight') browseMove(1); else if(k==='ArrowLeft') browseMove(-1); else if(confirm){ e.preventDefault(); peek(); } return; }
    if(missed){ if(confirm||k==='ArrowRight'||k==='2'){ e.preventDefault(); advance(); } return; }
    if(k==='ArrowRight'||k==='2') good(); else if(k==='ArrowLeft'||k==='1') again();
    else if(confirm){ e.preventDefault(); peek(); } });

  /* ---------------- settings ---------------- */
  function chips(id,items,active,toggle){ var box=d.getElementById(id); box.innerHTML='';
    items.forEach(function(it){ var b=d.createElement('button'); b.type='button'; b.textContent=it[1]; b.setAttribute('aria-pressed',active.indexOf(it[0])>=0);
      b.addEventListener('click',function(){ toggle(it[0]); }); box.appendChild(b); }); }
  function unitChips(){ var box=d.getElementById('s-units'); box.innerHTML='';
    (CFG.groups||[[null,ORDER]]).forEach(function(g){ var row=d.createElement('div'); row.className='chips'; box.appendChild(row);
      if(g[0]){ var on=g[1].filter(function(u){ return S.units.indexOf(u)>=0; }).length, all=on===g[1].length, b=d.createElement('button');   /* a whole book at once */
        b.type='button'; b.className='grp'; b.textContent=g[0]; b.setAttribute('aria-pressed',all?'true':on?'mixed':'false');
        b.addEventListener('click',function(){ S.units=S.units.filter(function(u){ return g[1].indexOf(u)<0; }).concat(all?[]:g[1]); persist(); start(); });
        row.appendChild(b); }
      g[1].forEach(function(u){ var b=d.createElement('button'); b.type='button'; b.textContent=CFG.units.filter(function(x){ return x[0]===u; })[0][1];
        b.setAttribute('aria-pressed',String(S.units.indexOf(u)>=0));
        b.addEventListener('click',function(){ var i=S.units.indexOf(u); if(i>=0) S.units.splice(i,1); else S.units.push(u); persist(); start(); });
        row.appendChild(b); }); }); }
  function renderSettings(){
    unitChips();
    chips('s-kinds',[['w','Wortschatz'],['g','Grammatik'],['r','Redemittel']],S.kinds,function(k){ var i=S.kinds.indexOf(k); if(i>=0) S.kinds.splice(i,1); else S.kinds.push(k); persist(); start(); });
    chips('s-dir',[['de','Deutsch → Englisch'],['en','Englisch → Deutsch']],[S.dir],function(v){ S.dir=v; persist(); renderSettings(); render(); });
    chips('s-new',[[5,'5'],[10,'10'],[15,'15'],[20,'20'],[25,'25'],[40,'40']],[S.perDay],function(v){ S.perDay=v; persist(); start(); });
    chips('s-round',[[10,'10'],[20,'20'],[0,'ohne Pause']],[S.round],function(v){ S.round=v; persist(); renderSettings(); });
    chips('s-mode',[[false,'Tagesplan'],[true,'Durchblättern']],[S.browse],function(v){ S.browse=v; persist(); start(); });
    chips('s-auto',[[true,'Ton an'],[false,'Ton aus']],[S.auto],function(v){ S.auto=v; persist(); renderSettings(); });
    var stat=d.getElementById('s-stat'); stat.innerHTML='';             /* every lesson, one line per book */
    (CFG.groups||[[null,ORDER]]).forEach(function(g){ var n={neu:0,lern:0,sicher:0,fest:0}, line=d.createElement('span');
      CARDS.forEach(function(c){ if(g[1].indexOf(c.u)<0||S.kinds.indexOf(c.k)<0) return; var s=state[c.id];
        if(!s) n.neu++; else if(s[0]<=2) n.lern++; else if(s[0]<=4) n.sicher++; else n.fest++; });
      line.className='line'; line.textContent=(g[0]?g[0]+': ':'')+'Neu '+n.neu+' · Lerne ich '+n.lern+' · Sicher '+n.sicher+' · Fest '+n.fest; stat.appendChild(line); }); }
  d.getElementById('all-u').addEventListener('click',function(){ S.units=S.units.length===ORDER.length?[]:ORDER.slice(); persist(); start(); });
  d.getElementById('save-btn').addEventListener('click',function(){
    var blob=new Blob([JSON.stringify({v:2,key:K,state:state,meta:meta,games:load('games',{})})],{type:'application/json'}), a=d.createElement('a');
    a.href=URL.createObjectURL(blob); a.download=K+'-fortschritt-'+new Date().toISOString().slice(0,10)+'.json'; d.body.appendChild(a); a.click(); a.remove(); });
  /* Laden adds a backup to the progress here, so the backups of two book apps both go into one course app: per card the
     state further on wins (the later due day, then the higher box), per game the better result, and two streaks that
     touch become one (12 days up to yesterday there and today here: 13). Cards this app does not have are left out. */
  function mergeIn(o){ var known={}, n=0, s=o.state, g=load('games',{}), og=o.games||{}, m=o.meta||{};
    CARDS.forEach(function(c){ known[c.id]=1; });
    Object.keys(s).forEach(function(id){ var a=state[id], b=s[id]; if(!known[id]||!Array.isArray(b)||b.length<2) return; n++;
      if(!a||b[1]>a[1]||(b[1]===a[1]&&b[0]>a[0])) state[id]=[+b[0],+b[1]]; });
    Object.keys(og).forEach(function(u){ if(!og[u]||typeof og[u]!=='object') return; g[u]=g[u]||{};
      Object.keys(og[u]).forEach(function(k){ var x=g[u][k]||{s:0,p:0}, y=og[u][k]||{}; g[u][k]={s:Math.max(x.s||0,y.s||0),p:Math.max(x.p||0,y.p||0)}; }); });
    if(typeof m.last==='number'&&m.streak>0){
      if(!(meta.streak>0)){ meta.streak=m.streak; meta.last=m.last; }
      else { var a=[meta.last-meta.streak+1,meta.last], b=[m.last-m.streak+1,m.last], late=a[1]>=b[1]?a:b, early=late===a?b:a;   /* [first day, last day] */
        meta.streak=late[0]<=early[1]+1?late[1]-Math.min(a[0],b[0])+1:late[1]-late[0]+1; meta.last=late[1]; } }
    save('srs',state); save('meta',meta); save('games',g); Games.refresh(); return n; }
  d.getElementById('load-in').addEventListener('change',function(e){ var f=e.target.files[0]; e.target.value=''; if(!f) return; var r=new FileReader();
    r.onload=function(){ var o=null; try{ o=JSON.parse(r.result); }catch(err){}
      if(!o||!o.state||typeof o.state!=='object'){ alert('Diese Datei ist keine Sicherung.'); return; }
      var n=mergeIn(o); start();
      alert(n?(n===1?'1 Karte aus der Sicherung übernommen.':'{n} Karten aus der Sicherung übernommen.'.replace('{n}',n))+' '+'Dein Fortschritt hier bleibt erhalten.'
             :'In dieser Sicherung ist kein Fortschritt für diese Lektionen.'); };
    r.readAsText(f); });

  /* ---------------- Spielen: five short games per unit, made from its cards ---------------- */
  var Games=(function(){
    var box=d.getElementById('g-box'), menu=d.getElementById('g-menu'), best=load('games',{}), timers=[], live=null, ac=null;
    var HAS_AUDIO=Object.keys(IDX).length>0;
    function later(f,ms){ timers.push(setTimeout(f,ms)); }
    function stop(){ timers.forEach(clearTimeout); timers=[]; if(live) live(); live=null; }
    function shuffle(a){ a=a.slice(); for(var i=a.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)), t=a[i]; a[i]=a[j]; a[j]=t; } return a; }
    function pick(a,n){ return shuffle(a).slice(0,Math.max(0,n)); }
    function esc(s){ return String(s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
    function el(tag,cls,markup){ var e=d.createElement(tag); if(cls) e.className=cls; if(markup!==undefined) e.innerHTML=markup; return e; }
    function btn(cls,markup,fn){ var b=el('button',cls,markup); b.type='button'; b.addEventListener('click',function(){ fn(b); }); return b; }
    function say(id){ if(HAS_AUDIO&&S.auto&&id){ stopAll(); clip(id); } }
    function canHear(){ return HAS_AUDIO&&S.auto; }
    function tone(at,from,to,type){
      try{ ac=ac||new (window.AudioContext||window.webkitAudioContext)(); var t=ac.currentTime+at, o=ac.createOscillator(), g=ac.createGain();
        o.type=type; o.frequency.setValueAtTime(from,t); o.frequency.exponentialRampToValueAtTime(to,t+0.14);
        g.gain.setValueAtTime(0.0001,t); g.gain.exponentialRampToValueAtTime(0.12,t+0.02); g.gain.exponentialRampToValueAtTime(0.0001,t+0.28);
        o.connect(g); g.connect(ac.destination); o.start(t); o.stop(t+0.3); }catch(e){} }
    function blip(ok){ if(navigator.vibrate) navigator.vibrate(ok?12:[30,40,30]); if(S.auto) tone(0,ok?587:196,ok?880:150,ok?'triangle':'sine'); }
    function chord(){ if(S.auto) [523,659,784].forEach(function(f,i){ tone(0.12+i*0.09,f,f*1.01,'triangle'); }); }   /* a streak of 3, 5, 10 … */
    function confetti(){ if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      var c=el('div','confetti'), colors=['#f2d36b','#34d399','#b19ac8','#7f9fbd','#c58fa3'];
      for(var i=0;i<46;i++){ var p=el('i'); p.style.left=(Math.random()*100)+'%'; p.style.background=colors[i%5];
        p.style.animationDelay=(Math.random()*0.35)+'s'; p.style.animationDuration=(1.1+Math.random()*0.9)+'s'; c.appendChild(p); }
      d.body.appendChild(c); setTimeout(function(){ c.remove(); },2600); }
    function marked(x){ var s=x.de, out='', at=0; x.t.forEach(function(sp){ out+=esc(s.slice(at,sp[0]))+'<mark>'+esc(s.slice(sp[0],sp[1]))+'</mark>'; at=sp[1]; }); return out+esc(s.slice(at)); }
    function cloze(x){ var s=x.de, out='', at=0; x.t.forEach(function(sp){ out+=esc(s.slice(at,sp[0]))+'<span class="gap">'+esc(s.slice(sp[0],sp[1]))+'</span>'; at=sp[1]; }); return out+esc(s.slice(at)); }
    function artLabel(v){ return v.aa?v.aa.join('/'):v.a; }
    function word(v){ return (v.a?'<span class="art-'+(COL[v.a]||v.a)+'">'+artLabel(v)+'</span> ':'')+esc(v.w); }
    function unit(){ return sel.value; }
    function data(){ return G[unit()]||{v:[],r:[],s:[]}; }
    /* every game: a progress bar, a 🔥 streak of right answers in a row, and at the end a round of just your mistakes */
    var run=0, top=0, runBox=null, drill=false;
    function head(title,timed){ box.innerHTML=''; var h=el('div','g-head'); h.appendChild(el('div','g-title',title)); var info=el('div','g-info','');
      h.appendChild(info); h.appendChild(btn('g-close','✕',function(){ open(); })); box.appendChild(h);
      var row=el('div','g-prog'), rail=el('div',timed?'g-rail g-clock':'g-rail'); info.bar=el('i'); rail.appendChild(info.bar);   /* a timed game: the bar is the clock */
      runBox=el('div','g-run',''); row.appendChild(rail); row.appendChild(runBox); box.appendChild(row);
      if(drill) box.appendChild(el('p','g-drill','Nur deine Fehler aus der letzten Runde.'));
      run=0; top=0; return info; }
    function step(info,i,n){ info.textContent=(i+1)+' / '+n; grow(info,i,n); }          /* question i+1 of n */
    function grow(info,k,n){ info.bar.style.width=Math.min(100,k/n*100)+'%'; }         /* k of n answered */
    function pulse(e){ if(!e) return; e.classList.remove('win'); void e.offsetWidth; e.classList.add('win'); }
    function cheer(ok,e){ if(!ok){ run=0; runBox.textContent=''; return; }
      run++; top=Math.max(top,run); pulse(e); if(run<2) return;
      runBox.textContent='🔥 '+run; runBox.classList.remove('bump'); void runBox.offsetWidth; runBox.classList.add('bump');
      if(run===3||run===5||run%10===0) chord(); }
    function note(list,x){ if(list.indexOf(x)<0) list.push(x); }                       /* a mistake to practise again */
    function stars(n){ return '★★★'.slice(0,n)+'☆☆☆'.slice(0,3-n); }
    function finish(key,got,score,lines,missed){ stop(); var u=unit(); best[u]=best[u]||{}; var old=best[u][key]||{s:0,p:0}, record=!drill&&old.p>0&&score>old.p;
      if(!drill){ best[u][key]={s:Math.max(old.s,got),p:Math.max(old.p,score)}; save('games',best); }   /* a mistakes round sets no record */
      if(top>=3&&key!=='art') lines=lines.concat(['🔥 Beste Serie: '+top]);
      box.innerHTML=''; var m=el('div','g-end'); m.appendChild(el('div','g-big',got>=3?'🏆':got===2?'🎉':'👍'));
      m.appendChild(el('div','g-stars',stars(got)));
      lines.forEach(function(l){ var p=el('p'); p.textContent=l; m.appendChild(p); });
      if(record) m.appendChild(el('p','g-rec','Neuer Rekord!'));
      var a=el('div','g-acts'), again=missed&&missed.length;
      if(again) a.appendChild(btn('main g-retry',fill('Fehler üben ({n})',{n:missed.length}),function(){ play(key,missed); }));
      a.appendChild(btn(again?'':'main','Nochmal',function(){ play(key); })); a.appendChild(btn('','Andere Spiele',function(){ open(); }));
      m.appendChild(a); box.appendChild(m); if(got>=3) confetti(); }
    /* Without spaces the browser finds the words (Intl.Segmenter): 。 stays with its word, kana after a kanji belong to it
       (食|べ → 食べ), and a sentence with a lone kana that is no particle (く|れ|て) was split badly and is left out. */
    var SEG=CFG.spaces===false&&window.Intl&&Intl.Segmenter?new Intl.Segmenter(d.documentElement.lang,{granularity:'word'}):null, SMALL=CFG.small||[];
    function toks(s){ s=s.trim(); if(CFG.spaces!==false) return s.split(/\s+/);
      var out=[], lead=''; if(SEG) Array.from(SEG.segment(s)).forEach(function(p){ var w=p.segment.trim(), last=out[out.length-1]; if(!w) return;
        if(!p.isWordLike){ if(out.length) out[out.length-1]+=w; else lead+=w; return; }
        if(last&&/^[ぁ-ゟ]+$/.test(w)&&/[㐀-鿿]$/.test(last)&&SMALL.indexOf(w)<0){ out[out.length-1]+=w; return; }
        out.push(lead+w); lead=''; });
      return out; }
    function broken(ws){ return CFG.spaces===false&&ws.some(function(w){ return /^[ぁ-ヿ]$/.test(w)&&SMALL.indexOf(w)<0; }); }
    function fill(s,o){ return s.replace(/\{(\w+)\}/g,function(m,k){ return o[k]; }); }      /* a sentence with numbers in it */
    function satzPool(g){ return g.s.filter(function(s){ var w=toks(s.de); return w.length>=5&&w.length<=9&&!broken(w); }); }   /* plain sentences of 5–9 words */
    function nouns(g){ return g.v.filter(function(v){ return v.a; }); }
    function pairPool(g){ var seen={}; return g.v.filter(function(v){ var k=(v.g||'').toLowerCase(); if(!k||seen[k]) return false; seen[k]=1; return true; }); }
    var LIST=[
      {k:'bingo',icon:'🎱',name:'Hör-Bingo',desc:'Hör einen Satz und finde das Wort auf deiner Karte.',ok:function(g){ return g.v.length>=4; },go:bingo},
      {k:'paare',icon:'🃏',name:'Wortpaare',desc:'Finde zu jedem Wort seine Bedeutung, so schnell du kannst.',ok:function(g){ return pairPool(g).length>=5; },go:paare},
      {k:'satz',icon:'🧩',name:'Satzbau',desc:'Tippe die Wörter in die richtige Reihenfolge.',ok:function(g){ return satzPool(g).length>=3; },go:satz},
      {k:'art',icon:'⚡',name:'Der · Die · Das',desc:'60 Sekunden: Welcher Artikel passt?',ok:function(g){ return ARTS.length>1&&nouns(g).length>=3; },go:artikel},
      {k:'red',icon:'💬',name:'Was sagt man?',desc:'Welche Wendung passt zur Situation?',ok:function(g){ return g.r.length>=3; },go:wendung}];
    function open(){ stop(); stopAll(); box.hidden=true; menu.hidden=false; var g=data(), u=unit(); menu.innerHTML='';
      menu.appendChild(el('p','g-lead',esc(CFG.labels[u]||u)+' als Spiel: ein paar Minuten, ganz ohne Lernstress.'));
      var ready=LIST.filter(function(x){ return x.ok(g); }), got=ready.reduce(function(n,x){ return n+((best[u]&&best[u][x.k]||{}).s||0); },0);
      if(ready.length) menu.appendChild(el('p','g-total',fill('★ {n} von {m} Sternen',{n:got,m:ready.length*3})));
      ready.forEach(function(x){ var b=best[u]&&best[u][x.k];
        menu.appendChild(btn('g-tile','<span class="g-icon">'+x.icon+'</span><span class="g-name">'+x.name+'</span><span class="g-desc">'+x.desc+'</span>'+
          '<span class="g-best">'+(b?stars(b.s)+(x.k==='art'||x.k==='paare'?' · Rekord '+b.p:''):'Neu')+'</span>',function(){ play(x.k); })); });
      if(ready.length>1) menu.appendChild(btn('g-random','🎲 Überrasch mich',function(){ play(ready[Math.floor(Math.random()*ready.length)].k); }));
      if(!ready.length) menu.appendChild(el('p','g-lead','Diese Lektion hat zu wenige Karten für ein Spiel.')); }
    function play(k,only){ stop(); stopAll(); var x=LIST.filter(function(y){ return y.k===k; })[0]; drill=!!only; menu.hidden=true; box.hidden=false; window.scrollTo(0,0); x.go(data(),only); }

    /* 🎱 Hör-Bingo: a sentence is played (or shown with a gap); tap a word of your card that it contains, or say none is there.
       Every call has one clear answer: its sentence holds no other word of the card (the build lists the words each sentence holds).
       A mistakes round puts the words you missed on the card. */
    function bingo(g,only){
      var vs=g.v.filter(function(v){ return v.x.length; }), n=vs.length>=12?9:vs.length>=8?6:4, cols=n===4?2:3, rows=n/cols;
      var board, places, calls, tries=0, ci=-1, open_=false, miss=0, wrong=0, bingoDone=false, on={}, readyAt=0, missed=[];
      function holds(x){ return places.map(function(p,k){ return x.m.indexOf(p)>=0?k:-1; }).filter(function(k){ return k>=0; }); }
      function call(v){ var own=board.indexOf(v), fit=v.x.filter(function(x){ return holds(x).every(function(k){ return k===own; }); });
        return fit.length?{v:v,x:pick(fit,1)[0]}:null; }
      function deal(){ var must=(only||[]).filter(function(v){ return vs.indexOf(v)>=0; }).slice(0,n);
        return shuffle(must.concat(pick(vs.filter(function(v){ return must.indexOf(v)<0; }),n-must.length))); }
      do { board=deal(); places=board.map(function(v){ return g.v.indexOf(v); }); calls=board.map(call); }
      while(calls.some(function(c){ return !c; })&&++tries<25);                   /* every word on the card can be called */
      var decoys=shuffle(vs.filter(function(v){ return board.indexOf(v)<0; })).map(call).filter(Boolean);
      calls=shuffle(calls.filter(Boolean).concat(decoys.slice(0,Math.ceil(n/2))));
      var info=head('🎱 Hör-Bingo');
      box.appendChild(el('p','g-lead',canHear()?'Hör den Satz. Kommt ein Wort deiner Karte darin vor? Tippe es an.':'Lies den Satz. Welches Wort fehlt? Ist es auf deiner Karte?'));
      var callBox=el('div','b-call'), cue=el('div','b-cue'); callBox.appendChild(cue);
      if(canHear()) callBox.appendChild(btn('b-again','🔊 Nochmal',function(){ if(ci>=0&&ci<calls.length) say(calls[ci].x.au); }));
      box.appendChild(callBox);
      var grid=el('div','b-grid'); grid.style.gridTemplateColumns='repeat('+cols+',1fr)';
      board.forEach(function(v,i){ grid.appendChild(btn('b-cell',word(v),function(b){ tap(i,b); })); });
      box.appendChild(grid); box.appendChild(btn('b-none','Nicht auf meiner Karte',function(b){ tap(-1,b); }));
      var fb=el('div','b-fb'), acts_=el('div','g-acts'); box.appendChild(fb); box.appendChild(acts_);
      function nextCall(){ ci++; wrong=0; fb.innerHTML=''; acts_.innerHTML=''; if(ci>=calls.length) return end();
        open_=true; readyAt=Date.now()+300; step(info,ci,calls.length);                /* a tap meant for the last call does not count */
        var x=calls[ci].x; if(canHear()&&x.au){ cue.innerHTML='<span class="b-ear">👂 Hör gut zu …</span>'; later(function(){ say(x.au); },300); } else cue.innerHTML=cloze(x); }
      function reveal(ok,text){ var x=calls[ci].x; open_=false; cue.innerHTML=marked(x); grow(info,ci+1,calls.length);
        fb.innerHTML='<div class="'+(ok?'g-ok':'g-no')+'">'+text+'</div><div class="b-tr">'+esc(x.en)+'</div>';
        if(ok) later(nextCall,1500); else acts_.appendChild(btn('main','Weiter ›',nextCall)); }         /* a mistake stays until you have read it */
      function stamp(i){ on[i]=1; grid.children[i].classList.add('on'); if(bingoDone) return; var lines=[], r, c, k;
        for(r=0;r<rows;r++){ var row=[]; for(c=0;c<cols;c++) row.push(r*cols+c); lines.push(row); }
        if(rows>2) for(c=0;c<cols;c++){ var col=[]; for(r=0;r<rows;r++) col.push(r*cols+c); lines.push(col); }
        if(rows===cols){ var a=[], b=[]; for(k=0;k<cols;k++){ a.push(k*cols+k); b.push(k*cols+cols-1-k); } lines.push(a,b); }
        if(lines.some(function(line){ return line.every(function(j){ return on[j]; }); })){ bingoDone=true; var big=el('div','b-bingo','BINGO!'); d.body.appendChild(big); confetti(); later(function(){ big.remove(); },1500); } }
      function shake(b){ b.classList.add('shake'); setTimeout(function(){ b.classList.remove('shake'); },400); }
      function tap(i,b){ if(!open_||Date.now()<readyAt) return; var c=calls[ci], own=board.indexOf(c.v), hits=holds(c.x);
        if(own>=0&&hits.indexOf(own)<0) hits.push(own);
        if(i>=0&&hits.indexOf(i)>=0){ blip(true); stamp(i); cheer(true,b); reveal(true,'✓ '+word(board[i])); return; }   /* any word of the card it contains */
        if(i<0&&!hits.length){ blip(true); cheer(true,b); reveal(true,'✓ Richtig, '+word(c.v)+' ist nicht auf deiner Karte.'); return; }
        blip(false); miss++; shake(b); cheer(false); note(missed,c.v);
        if(i>=0&&hits.length&&++wrong<2) return;                                 /* another cell: look again, once */
        hits.forEach(function(k){ var cell=grid.children[k]; cell.classList.add('hint'); later(function(){ cell.classList.remove('hint'); },2000); stamp(k); });
        reveal(false,hits.length?'Auf deiner Karte: '+hits.map(function(k){ return word(board[k]); }).join(', '):'Nicht auf deiner Karte: '+word(c.v)); }
      function end(){ finish('bingo',miss===0?3:miss<=2?2:1,Math.max(0,n*10-miss*3),[(bingoDone?'Bingo! ':'')+'Fehler: '+miss,
        fill(canHear()?'Du hast {n} Sätze gehört und {w} Wörter gefunden.':'Du hast {n} Sätze gelesen und {w} Wörter gefunden.',{n:calls.length,w:n})],missed); }
      nextCall(); }

    /* 🧩 Satzbau: the English meaning is shown; tap the German words in order (a wrong tile just shakes) */
    function satz(g,only){
      var round=only?shuffle(only):pick(satzPool(g),6), i=-1, clean=0, missed=[], info=head('🧩 Satzbau');
      box.appendChild(el('p','g-lead','Bau den deutschen Satz: Tippe die Wörter der Reihe nach an.'));
      var prompt=el('div','s-prompt'), line=el('div','s-line'), tiles=el('div','s-tiles'), fb=el('div','s-fb'), acts_=el('div','g-acts');
      [prompt,line,tiles,fb,acts_].forEach(function(e){ box.appendChild(e); });
      function nextSentence(){ i++; if(i>=round.length) return finish('satz',clean===round.length?3:clean>=Math.ceil(round.length*0.6)?2:1,clean*10,['Fehlerfrei: '+clean+' von '+round.length+' Sätzen'],missed);
        var s=round[i], want=toks(s.de), at=0, errs=0, order; step(info,i,round.length);
        prompt.textContent=s.en; line.innerHTML=''; tiles.innerHTML=''; fb.innerHTML=''; acts_.innerHTML='';
        if(canHear()&&s.au) acts_.appendChild(btn('','🔊 Anhören',function(){ say(s.au); }));
        do { order=shuffle(want.map(function(w,k){ return k; })); } while(want.length>2&&order.every(function(k,j){ return want[k]===want[j]; }));
        order.forEach(function(k){ var t=btn('s-tile',esc(want[k]),function(b){ choose(b); }); t.setAttribute('data-w',want[k]); tiles.appendChild(t); });
        function choose(t){ if(t.disabled||at>=want.length) return;
          if(t.getAttribute('data-w')===want[at]){ t.disabled=true; t.classList.add('used'); line.appendChild(el('span','s-word',esc(want[at]))); at++;
            [].forEach.call(tiles.children,function(x){ x.classList.remove('hint'); });
            if(at===want.length){ if(!errs) clean++; else note(missed,s); solved(s,errs); } return; }
          errs++; blip(false); cheer(false); t.classList.add('shake'); setTimeout(function(){ t.classList.remove('shake'); },400);
          if(errs>=2) [].some.call(tiles.children,function(x){ if(!x.disabled&&x.getAttribute('data-w')===want[at]){ x.classList.add('hint'); return true; } return false; }); } }
      function solved(s,errs){ blip(true); line.innerHTML='<span>'+marked(s)+'</span>'; say(s.au); grow(info,i+1,round.length); if(!errs) cheer(true,line);
        fb.innerHTML=errs?'<span class="g-no">'+(errs>1?fill('Geschafft, mit {n} Fehlern.',{n:errs}):'Geschafft, mit 1 Fehler.')+'</span>':'<span class="g-ok">✓ Perfekt!</span>';
        acts_.innerHTML=''; if(canHear()&&s.au) acts_.appendChild(btn('','🔊 Nochmal',function(){ say(s.au); })); acts_.appendChild(btn('main','Weiter ›',nextSentence)); }
      nextSentence(); }

    /* ⚡ Der · Die · Das: 60 seconds of nouns; a streak multiplies the points, a miss comes back soon.
       A mistakes round has no clock: every noun you missed comes twice, and a miss brings it back once more. */
    function artikel(g,only){
      var pool_=only||nouns(g); if(!only&&pool_.length<12){ var more=[]; ORDER.forEach(function(u){ if(u!==unit()&&G[u]) more=more.concat(nouns(G[u])); }); pool_=pool_.concat(pick(more,12-pool_.length)); }
      var q_=only?shuffle(only).concat(shuffle(only)):shuffle(pool_), need=q_.length, rights=0, cur_=null, score=0, misses=[], left=60, wait=false, readyAt=0;
      var info=head('⚡ Der · Die · Das',!only), time=info.bar;
      var sc=el('div','a-score'), card=el('div','a-card'); box.appendChild(sc); box.appendChild(card);
      var row=el('div','a-btns'); row.style.gridTemplateColumns='repeat('+ARTS.length+',1fr)';
      ARTS.forEach(function(a){ row.appendChild(btn('a-'+(COL[a]||a),a,function(){ answer(a); })); }); box.appendChild(row);
      function key(e){ var a=ARTS[+e.key-1]; if(a&&!e.repeat){ e.preventDefault(); answer(a); } }
      d.addEventListener('keydown',key);
      var tm=only?0:setInterval(function(){ left--; time.style.width=(left/60*100)+'%'; info.textContent=left+' s'; if(left<=0) over(); },1000);
      live=function(){ clearInterval(tm); d.removeEventListener('keydown',key); };
      function mult(){ return Math.min(4,1+Math.floor(run/3)); }
      function showNext(){ if(!q_.length){ if(only) return over(); q_=shuffle(pool_); } cur_=q_.shift();
        card.innerHTML='<div class="a-word">'+esc(cur_.w)+'</div><div class="a-gloss">'+esc(cur_.g)+'</div>'; sc.textContent=score+' Punkte'+(mult()>1?' · ×'+mult():'');
        readyAt=Date.now()+300; }                                                  /* a tap meant for the last word does not count */
      function answer(a){ if(wait||left<=0||Date.now()<readyAt) return; wait=true;
        if((cur_.aa||[cur_.a]).indexOf(a)>=0){ score+=10*mult(); rights++; cheer(true,card); blip(true); say(cur_.h); card.classList.add('good');
          if(only){ info.textContent=rights+' / '+need; grow(info,rights,need); }
          later(function(){ card.classList.remove('good'); wait=false; if(left>0) showNext(); },260); return; }
        cheer(false); blip(false); misses.push(cur_); q_.splice(Math.min(4,q_.length),0,cur_);
        card.innerHTML='<div class="a-word">'+word(cur_)+'</div><div class="a-gloss">'+esc(cur_.g)+'</div>'; card.classList.add('bad'); say(cur_.h);
        later(function(){ card.classList.remove('bad'); wait=false; if(left>0) showNext(); },1600); }
      function over(){ var seen={}, list=misses.filter(function(v){ var k=v.a+' '+v.w; if(seen[k]) return false; seen[k]=1; return true; });
        var got=only?(!list.length?3:list.length<=2?2:1):score>=300?3:score>=150?2:1;
        finish('art',got,score,[score+' Punkte · beste Serie '+top].concat(list.length?['Merk dir: '+list.map(function(v){ return artLabel(v)+' '+v.w; }).join(', ')]:['Kein einziger Fehler!']),list); }
      info.textContent=only?'0 / '+need:'60 s'; showNext(); }

    /* 💬 Was sagt man?: a situation, three phrases from the lesson; pick the one that fits */
    function wendung(g,only){
      var all=g.r, qs=only?shuffle(only):pick(all,Math.min(8,all.length)), i=-1, right=0, missed=[], info=head('💬 Was sagt man?');
      box.appendChild(el('p','g-lead','Lies die Situation und wähle die passende Wendung.'));
      var sit=el('div','r-sit'), opts=el('div','r-opts'), fb=el('div','r-fb'), acts_=el('div','g-acts');
      [sit,opts,fb,acts_].forEach(function(e){ box.appendChild(e); });
      function others(r){ var seen={}; seen[r.f]=1;                             /* two other phrases, never the same words twice */
        function fresh(x){ if(seen[x.f]) return false; seen[x.f]=1; return true; }
        var o=shuffle(all.filter(function(x){ return x.grp!==r.grp; })).filter(fresh);
        if(o.length<2) o=o.concat(shuffle(all.filter(function(x){ return x.grp===r.grp; })).filter(fresh));
        if(o.length<2) ORDER.forEach(function(u){ if(u!==unit()&&G[u]) o=o.concat(shuffle(G[u].r).filter(fresh)); });
        return o.slice(0,2); }
      function ask(){ i++; if(i>=qs.length) return finish('red',right===qs.length?3:right>=Math.ceil(qs.length*0.6)?2:1,right*10,['Richtig: '+right+' von '+qs.length],missed);
        var r=qs[i], answered=false; step(info,i,qs.length); fb.innerHTML=''; acts_.innerHTML='';
        sit.innerHTML='<div>'+esc(r.w)+'</div>'+(r.reg?'<div class="r-reg">'+esc(r.reg)+'</div>':''); opts.innerHTML='';
        shuffle([r].concat(others(r))).forEach(function(x){ opts.appendChild(btn('r-opt',esc(x.f),function(b){ if(answered) return; answered=true; grow(info,i+1,qs.length);
          if(x===r){ right++; blip(true); b.classList.add('ok'); cheer(true,b); }
          else { blip(false); cheer(false); note(missed,r); b.classList.add('no'); [].forEach.call(opts.children,function(o,k){ if(o.textContent===r.f) o.classList.add('ok'); }); }
          say(r.au); fb.innerHTML='<div class="'+(x===r?'g-ok':'g-no')+'">'+(x===r?'✓ Genau!':'So sagt man es:')+' '+esc(r.g)+'</div><div>'+marked(r.x)+'</div><div class="b-tr">'+esc(r.x.en)+'</div>';
          acts_.appendChild(btn('main','Weiter ›',ask)); })); }); }
      ask(); }

    /* 🃏 Wortpaare: tap a German word, then its meaning; up to three rounds of three to five pairs against the clock.
       A mistakes round deals the words you mixed up, with others to make five. */
    function paare(g,only){
      var all=pairPool(g), pool_=only?only.concat(pick(all.filter(function(v){ return only.indexOf(v)<0; }),5-only.length)):pick(all,15);
      var sets=[], k, at=0, rounds=Math.ceil(pool_.length/5), round=-1, misses=0, missed=[], matched=0, t0=Date.now(), info=head('🃏 Wortpaare');
      for(k=0;k<rounds;k++){ var size=Math.ceil((pool_.length-at)/(rounds-k)); sets.push(pool_.slice(at,at+size)); at+=size; }   /* 7 pairs: 4 + 3 */
      box.appendChild(el('p','g-lead','Tippe ein deutsches Wort und dann seine Bedeutung.'));
      var grid=el('div','p-grid'), left=el('div','p-col'), right=el('div','p-col'); grid.appendChild(left); grid.appendChild(right); box.appendChild(grid);
      function deal(){ round++; if(round>=sets.length) return done(); var set=sets[round], picked=null, paired=0;
        info.textContent='Runde '+(round+1)+' / '+sets.length; grow(info,matched,pool_.length); left.innerHTML=''; right.innerHTML='';
        shuffle(set).forEach(function(v){ left.appendChild(card(v,'de',word(v))); });
        shuffle(set).forEach(function(v){ right.appendChild(card(v,'en',esc(v.g))); });
        function card(v,side,markup){ var b=btn('p-card p-'+side,markup,function(){ choose(b,v,side); }); return b; }
        function choose(b,v,side){ if(b.disabled) return;
          if(!picked||picked.side===side){ if(picked) picked.b.classList.remove('sel'); picked={b:b,v:v,side:side}; b.classList.add('sel'); if(side==='de') say(v.h); return; }
          var a=picked; picked=null;
          if(a.v===v){ blip(true); cheer(true,b); pulse(a.b); grow(info,++matched,pool_.length);
            [a.b,b].forEach(function(x){ x.classList.remove('sel'); x.classList.add('done'); x.disabled=true; });
            if(++paired===set.length) later(deal,450); return; }
          blip(false); cheer(false); misses++; note(missed,a.v); [a.b,b].forEach(function(x){ x.classList.remove('sel'); x.classList.add('shake'); setTimeout(function(){ x.classList.remove('shake'); },400); }); } }
      function done(){ var secs=Math.round((Date.now()-t0)/1000), n=pool_.length;
        finish('paare',misses===0&&secs<=n*4?3:misses<=Math.ceil(n/5)?2:1,Math.max(10,n*20-secs*2-misses*10),['Zeit: '+secs+' s · Fehler: '+misses],missed); }
      deal(); }
    return {open:open, stop:stop, refresh:function(){ best=load('games',{}); }};   /* refresh: after Laden */
  })();

  var early=d.getElementById('early-unit'); if(early) early.remove();   /* the unit shown while the page loaded */
  show(ui.unit||units[0].id,false);
  mode(ui.tab==='p'||ui.tab==='g'?ui.tab:'l');
})();
"""

PRACTICE = """
<section id="practice" class="pr" aria-label="Üben">
<div class="tr-top"><div class="tr-bar"><i id="tr-fill"></i></div><span class="tr-count" id="tr-count"></span><span class="tr-streak" id="tr-streak"></span></div>
<div class="fc" id="fc" aria-live="polite"></div>
<div class="dock"><div class="acts" id="acts"></div><div class="undo" id="undo" aria-live="polite"></div></div>
<details class="settings"><summary>Einstellungen</summary>
<div class="group"><div class="lab">Lektionen <button type="button" id="all-u" style="min-height:28px;padding:2px 8px;font-size:12px;margin-left:6px">alle / keine</button></div><div id="s-units"></div>
<p class="stat">Neue Karten kommen aus den gewählten Lektionen. Fällige Karten kommen aus allen, damit du nichts vergisst.</p></div>
<div class="group"><div class="lab">Teile</div><div class="chips" id="s-kinds"></div></div>
<div class="group"><div class="lab">Richtung (Wortschatz)</div><div class="chips" id="s-dir"></div></div>
<div class="group"><div class="lab">Neue Karten pro Tag</div><div class="chips" id="s-new"></div></div>
<div class="group"><div class="lab">Pause nach … Karten</div><div class="chips" id="s-round"></div></div>
<div class="group"><div class="lab">Modus</div><div class="chips" id="s-mode"></div></div>
<div class="group"><div class="lab">Ton (Aussprache und Spiele)</div><div class="chips" id="s-auto"></div></div>
<div class="group"><div class="lab">Fortschritt</div><p class="stat" id="s-stat"></p>
<div class="backup"><button type="button" id="save-btn">Sichern</button><label for="load-in">Laden</label><input type="file" id="load-in" accept="application/json,.json"></div>
<p class="stat">Der Fortschritt bleibt in diesem Browser auf diesem Gerät. Mit „Sichern“ nimmst du ihn mit.</p></div>
</details>
</section>
"""

GAMES = """
<section id="games" aria-label="Spielen">
<div class="g-menu" id="g-menu"></div>
<div class="g-box" id="g-box" hidden></div>
</section>
"""


FRAME = """<nav class="bar" aria-label="Navigation">
<div class="tabs"><button type="button" id="tab-l" aria-pressed="true">Lernen</button><button type="button" id="tab-p" aria-pressed="false">Üben</button><button type="button" id="tab-g" aria-pressed="false">Spielen</button></div>
<button class="nav lern-only" id="prev" type="button" aria-label="Vorherige Lektion">‹</button>
<select class="lern-only" id="pick" aria-label="Lektion wählen">__OPTIONS__</select>
<button class="nav lern-only" id="next" type="button" aria-label="Nächste Lektion">›</button>
<input class="lern-only search-only" id="q" type="search" placeholder="Suchen…" aria-label="Suchen">
<div class="hits lern-only search-only" id="hits"></div>
</nav>
<noscript><p class="cover">Audio, Üben und Spielen brauchen einen Browser mit JavaScript.</p></noscript>"""


# Runs in <head>, before any unit is read: every unit but the one the learner was on stays hidden while the page loads,
# so a phone never lays out the whole course (that took longer than the reading itself). The app script takes over.
EARLY_JS = """<script>(function(){ var r=document.documentElement, u={}; r.classList.add('js');
  try{ u=JSON.parse(localStorage.getItem('__KEY__:ui'))||{}; }catch(e){}
  if(u.tab==='p'||u.tab==='g') return; var s=document.createElement('style'); s.id='early-unit';
  s.textContent='section.unit[id="'+(typeof u.unit==='string'&&/^[A-Za-z0-9_-]+$/.test(u.unit)?u.unit:'__FIRST__')+'"]{display:block}';
  document.head.appendChild(s); })();</script>"""
# Right after the bar: it shows the tab and unit the learner was on from the first paint, not only once the app runs.
EARLY_BAR = """<script>(function(){ var u={}, d=document; try{ u=JSON.parse(localStorage.getItem('__KEY__:ui'))||{}; }catch(e){}
  var t=u.tab==='p'||u.tab==='g'?u.tab:'l', id=typeof u.unit==='string'&&/^[A-Za-z0-9_-]+$/.test(u.unit)?u.unit:'', p=d.getElementById('pick');
  ['l','p','g'].forEach(function(k){ d.getElementById('tab-'+k).setAttribute('aria-pressed',String(k===t)); });
  if(t!=='l') d.body.classList.add(t==='p'?'mode-practice':'mode-games');
  if(id&&p.querySelector('option[value="'+id+'"]')) p.value=id; })();</script>"""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "course"


def plain(fragment):
    """Visible text of a card fragment, without its audio buttons (the one-line answer shown after a quick ✓)."""
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<button.*?</button>", "", fragment, flags=re.S))
    return " ".join(html.unescape(text).split())


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build(course, output, audio=True, bitrate="32k", explain_bitrate="24k", placeholder_audio=False):
    prof = course.get("profile") or language.profile("de")
    ui = language.ui_table(prof)
    plan = build_course_plan(course)[1] if audio else None
    css, sections, options, cards = None, [], [], []
    sequences, examples, stories, games = {}, {}, {}, {}
    used_german, used_explain, first_unit = set(), set(), {}
    for unit in course["units"]:
        uid, label = unit["id"], unit["label"]
        page = unit["sheet"].read_text(encoding="utf-8")
        require('name="study-pack-status" content="reviewed"' in page, f"{uid}: only reviewed sheets go into the app")
        lesson = json.loads(unit["lesson"].read_text(encoding="utf-8-sig"))
        css = css or re.search(r"<style>(.*?)</style>", page, re.S).group(1)
        unit_plan = plan["units"][uid] if audio else None
        page = write_explanations(page, lesson, course.get("narration", {}).get(uid), unit_plan,
                                  course["cache"] if audio and not placeholder_audio else None, prof, ui)
        if audio:
            page = add_audio_buttons(page, lesson, unit_plan, used_german, prof, ui)
            sequences[uid] = listening_order(f"{uid}-", lesson, unit_plan)
            examples[uid] = examples_order(f"{uid}-", lesson, unit_plan)
            stories[uid] = story_order(f"{uid}-", unit_plan)
            for chain in list(unit_plan["explain"].values()) + list(unit_plan.get("explain_en", {}).values()):
                used_explain.update(chain)
            used_german.update([unit_plan["title"]] + list(unit_plan["sections"].values()))
            for cid in used_german | used_explain:
                first_unit.setdefault(cid, len(sections))
        page = number_examples(page, lesson)
        games[uid] = game_data(lesson, unit_plan)
        body = re.search(r'<main class="wrap">(.*?)</main>', page, re.S).group(1)
        if audio:
            body = body.replace("</header>", f'<div class="listen-row"><button type="button" class="listen-open" data-unit="{uid}">'
                                             f'{html.escape(ui.get("🎧 Anhören", "🎧 Anhören"))}</button></div></header>', 1)
        title = html.unescape(re.search(r"<h1>(.*?)</h1>", body).group(1))
        options.append((uid, f'<option value="{uid}">{html.escape(label)} · {html.escape(title.split(" – ")[0])}</option>'))
        for kind, cid, inner in re.findall(r'<article class="(voc|rule|phrase)" id="([^"]+)">(.*?)</article>', body, re.S):
            card = {"u": uid, "l": label, "id": f"{uid}-{cid}", "k": KIND[kind], "b": inner}
            if kind == "voc":
                m = re.search(r'<span class="de">(.*?)</span>(?:<button[^>]*>.*?</button>)?<span class="en">(.*?)</span>', inner, re.S)
                card.update(f=m.group(1), r=m.group(2), a=f"{plain(m.group(1))} = {plain(m.group(2))}")
                if audio:
                    card["fa"] = unit_plan["controls"][f"{cid}-head"]
            elif kind == "rule":
                card["f"] = re.sub(r"<button.*?</button>", "", re.search(r"<h3>(.*?)</h3>", inner, re.S).group(1), flags=re.S)
                card["a"] = plain(card["f"])
            else:
                meaning = re.search(r'<p class="meaning">(.*?)</p>', inner, re.S).group(1)
                when = re.search(r'<div class="when">(.*?)</div>', inner, re.S).group(1)
                card["f"] = f'<span class="q-mean">{meaning}</span><span class="q-when">{when}</span>'
                card["a"] = plain(re.search(r'<div class="head">(.*?)</div>', inner, re.S).group(1))
                if audio:
                    card["ba"] = unit_plan["controls"][f"{cid}-head"]
            cards.append(card)
        body = re.sub(r' id="([^"]+)"', lambda m: f' id="{uid}-{m.group(1)}"', body)
        sections.append(f'<section class="unit" id="{uid}">{body}</section>')

    payloads = {}
    if audio and not placeholder_audio:
        ff = ffmpeg_exe()
        jobs = [(cid, bitrate) for cid in sorted(used_german)] + [(cid, explain_bitrate) for cid in sorted(used_explain - used_german)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            for cid, data in zip([j[0] for j in jobs], pool.map(lambda j: compressed(course["cache"], j[0], j[1], ff), jobs)):
                payloads[cid] = data
    groups = []                                       # books in one course: [label, unit ids], in course order
    for unit in course["units"]:
        if unit.get("group"):
            if not groups or groups[-1][0] != unit["group"]:
                groups.append([unit["group"], []])
            groups[-1][1].append(unit["id"])
    picker = dict(options)
    options_html = ("".join(f'<optgroup label="{html.escape(name)}">' + "".join(picker[u] for u in ids) + "</optgroup>"
                            for name, ids in groups) if groups else "".join(option for _, option in options))
    config = {"key": slug(course["title"]), "perDay": int(course.get("new_per_day", 20)),
              "units": [[u["id"], u["id"]] for u in course["units"]], "labels": {u["id"]: u["label"] for u in course["units"]},
              "arts": prof["articles"], "col": prof["article_colours"]}
    if groups:
        config["groups"] = groups
    if not language.spaced(prof):                     # Satzbau asks the browser for the words (Intl.Segmenter)
        config.update(spaces=False, small=prof["bingo"]["function_words"].split())
    rtl = study_pack.RTL_CSS + RTL_APP_CSS if prof.get("direction") == "rtl" else ""
    blocks = {}
    for cid, data in payloads.items():
        blocks.setdefault(first_unit[cid], []).append(f"{cid}:{data}")
    audio_blocks = "".join(f'<script type="text/plain" id="au-{k}">{";".join(v)}</script>\n' for k, v in sorted(blocks.items()))
    index = {cid: first_unit[cid] for cid in payloads}
    js = (language.localize(APP_JS.replace("__LISTEN__", LISTEN_JS), ui)
          .replace("__INDEX__", json.dumps(index, separators=(",", ":")))
          .replace("__SEQUENCES__", compact(sequences))
          .replace("__EXAMPLES__", compact(examples))
          .replace("__STORIES__", compact(stories))
          .replace("__CARDS__", compact(cards))
          .replace("__ORDER__", json.dumps([u["id"] for u in course["units"]]))
          .replace("__CONFIG__", compact(config))
          .replace("__GAME__", compact(games)))
    names = prof["sections"]
    subtitle = html.escape(course.get("subtitle", f"{len(course['units'])} {ui.get('Lektionen', 'Lektionen')} · "
                                                  f"{names['vocabulary']} · {names['grammar']} · {names['redemittel']}"))
    frame = (language.localize(FRAME, ui).replace("__OPTIONS__", options_html)
             .replace("</nav>", "</nav>\n" + EARLY_BAR.replace("__KEY__", config["key"]), 1))
    early = EARLY_JS.replace("__KEY__", config["key"]).replace("__FIRST__", course["units"][0]["id"])
    doc = f"""<!DOCTYPE html>
<html lang="{prof['code']}"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="study-pack-app" content="course v2">
<title>{html.escape(course['title'])}</title>
<style>{css}{AUDIO_CSS}{APP_CSS}{rtl}</style>
{early}
</head>
<body><main class="wrap">
{frame}
<div class="lernen">
<div class="cover"><b>{html.escape(course['title'])}</b>{subtitle}</div>
{''.join(sections)}
</div>
{language.localize(PRACTICE, ui)}
{language.localize(GAMES, ui)}
{language.localize(LISTEN_HTML, ui)}
</main>
<script>{js}</script>
{audio_blocks}
</body></html>
"""
    require("http://" not in doc and "https://" not in doc, "output unexpectedly contains an external URL")
    visible = re.sub(r'<script type="text/plain".*?</script>', "", doc, flags=re.S)       # without the audio, once
    for term in course.get("private_terms", []):
        require(not exact_term(visible, term), f"the app names the private source term {term!r}")
    output = Path(output)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(doc)
    return {"cards": len(cards), "clips": len(payloads), "bytes": output.stat().st_size}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--course", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-audio", action="store_true", help="Study, practice and games only, no embedded audio")
    parser.add_argument("--bitrate", default="32k", help="German clips (default 32k)")
    parser.add_argument("--explain-bitrate", default="24k", help="spoken grammar explanations (default 24k)")
    parser.add_argument("--placeholder-audio", action="store_true", help=argparse.SUPPRESS)  # silent buttons, for tests/screenshots
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), "output exists; choose a new versioned filename")
        require(args.output.suffix.lower() == ".html", "output must be an .html file")
        course = load_course(args.course)
        result = build(course, args.output, audio=not args.no_audio, bitrate=args.bitrate,
                       explain_bitrate=args.explain_bitrate, placeholder_audio=args.placeholder_audio)
        print(f"WROTE: {args.output} ({result['bytes'] / 1e6:.1f} MB): {len(course['units'])} units, "
              f"{result['cards']} cards, {result['clips']} embedded clips")
        return 0
    except (AudioError, speech.SpeechError, study_pack.PackError, OSError, json.JSONDecodeError,
            subprocess.CalledProcessError, AttributeError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
