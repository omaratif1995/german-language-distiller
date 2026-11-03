#!/usr/bin/env python3
"""Embed clear neural lesson audio and playback controls in a study-sheet copy.

The script sends the lesson's selected learner text to the configured Edge TTS
service during synthesis. It therefore requires an explicit confirmation flag.
The output itself is a single offline HTML file with no external media URLs.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import difflib
import html
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import language  # noqa: E402
import speech  # noqa: E402
from study_pack import story_sentences  # noqa: E402

def sections_of(lesson):
    """The section names of the lesson's language, also spoken as section titles (Wortschatz … for German)."""
    return language.profile(lesson.get("target_language", "de"))["sections"]


class AudioError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AudioError(message)


def esc(value):
    return html.escape(str(value), quote=True)


def speakable(value, lang="de"):
    """Turn visual lesson notation into text a voice can read naturally (see speech.speakable)."""
    return speech.speakable(value, lang)


Clip = speech.Clip


def voices_of(voices):
    """Accept a {"de": ..., "en": ...} mapping, or one voice name for both (tests, old callers)."""
    if voices is None:
        return dict(speech.DEFAULT_VOICES)
    if isinstance(voices, str):
        return {"de": voices, "en": voices}
    require(set(voices) >= {"de", "en"}, "voices needs a German ('de') and an English ('en') voice")
    return dict(voices)


# ---------------------------------------------------------------- written explanations ---
# A narration is written in short blocks, one per line: a plain line is a paragraph, "> " an example and "! " a
# careful-now note. «…» marks the language's own words (in the English backup it also tells the voice to switch).
# The voice reads the lines as one text; the course app shows the blocks and lights up the sentence being read.
def explanation_blocks(text):
    """[(kind, body)]: kind "p" (paragraph), "ex" (example) or "warn" (careful)."""
    found = []
    for line in str(text).splitlines():
        line = line.strip()
        kind = {">": "ex", "!": "warn"}.get(line[:1]) if line[1:2] == " " else None
        if line:
            found.append((kind or "p", line[2:].strip() if kind else line))
    return found


def explanation_speech(text, marked=False):
    """What the voice reads: the blocks as one text, with «…» kept only where they choose the voice (marked)."""
    spoken = " ".join(body for _, body in explanation_blocks(text))
    return spoken if marked else spoken.replace("«", "").replace("»", "")


def explanation_sentences(text, prof=None):
    """[(kind, [sentences])] per block, split as story sentences are, but never inside «…» (a run of German forms
    with full stops in it stays one sentence)."""
    found = []
    for kind, body in explanation_blocks(text):
        sentences = []
        for sentence in story_sentences(body, prof or language.profile("de")) or [body]:
            if sentences and sentences[-1].count("«") > sentences[-1].count("»"):
                sentences[-1] += " " + sentence
            else:
                sentences.append(sentence)
        found.append((kind, sentences))
    return found


def sentence_times(sentences, words):
    """When each sentence starts (s), from the voice's word timings [(seconds, word)]. The written letters are
    aligned with the spoken ones, so a symbol read out, or a word the voice says differently, changes nothing."""
    letters = lambda text: [c for c in text.casefold() if c.isalnum()]   # noqa: E731
    shown, starts = [], []
    for sentence in sentences:
        starts.append(len(shown))
        shown += letters(sentence)
    said, owner = [], []
    for index, (_, word) in enumerate(words):
        chars = letters(word)
        said += chars
        owner += [index] * len(chars)
    if not said:
        return []
    found = {}
    for a, b, size in difflib.SequenceMatcher(None, shown, said, autojunk=False).get_matching_blocks():
        found.update((a + k, owner[b + k]) for k in range(size))
    times = []
    for start, end in zip(starts, starts[1:] + [len(shown)]):
        hit = next((found[k] for k in range(start, end) if k in found), None)
        times.append(max(words[hit][0] if hit is not None else 0.0, times[-1] if times else 0.0))
    return times


def build_plan(lesson, voices=None, narration=None):
    """Clips, listening order, per-card controls and the spoken grammar explanations of one lesson.

    Target-language text goes to the target voice (German: de-DE-KatjaNeural), English text to the English voice;
    target-language words inside English text are detected and spoken by the target voice.

    Grammar is explained by one narrator (`voices["narrator"]`, a voice that speaks both languages, at
    `voices["narrator_rate"]`, a little slower), so the explanation sounds like one teacher. `narration` maps grammar
    ids to authored explanations: {"de": the explanation in the target language, "en": an English backup with
    target-language words marked «…»}, or a string (English only), written in blocks (explanation_blocks); a
    "title" and "patterns" in the target language are for the written card only. The target-language one is played
    and listened to; the English one waits behind an EN button. Both are timed, so the card can follow the voice.
    Without narration, meaning, rule, patterns and contrast are read.
    Returns (clips, sequence, controls, explain, explain_en).
    """
    voices, narration, names = voices_of(voices), narration or {}, sections_of(lesson)
    clips, sequence, controls, explain, explain_en = {}, [], {}, {}, {}
    teacher = {lang: voices.get("narrator") or voices[lang] for lang in ("de", "en")}
    pace = voices.get("narrator_rate", "")

    def add(value, kind, control=None, who=None, rate="", listed=True, timed=False):
        clip = speech.make_clip(value, kind, who or voices, rate, timed)
        clips.setdefault(clip.clip_id, clip)
        if listed:                                    # part of the lesson's listening order
            sequence.append(clip.clip_id)
        if control:
            require(control not in controls, f"Duplicate audio control {control}")
            controls[control] = clip.clip_id
        return clip.clip_id

    add(lesson["title"], "de")
    add(names["vocabulary"], "de")
    previous = None
    for record in lesson["vocabulary"]:
        if record["group"] != previous:
            add(record["group"], "de")
            previous = record["group"]
        head = ((record.get("article", "") + " ") if record.get("article") else "") + record["lemma"]
        add(head, "de", f'{record["id"]}-head')
        add(record["gloss"], "en")
        if record.get("forms", "").strip():
            add(record["forms"], "mix-de")
        for index, example in enumerate(record["examples"]):
            add(example["de"], "de", f'{record["id"]}-ex-{index}')
            add(example["en"], "en")

    add(names["grammar"], "de")
    for record in lesson["grammar"]:
        gid = record["id"]
        told = narration.get(gid) or {}
        told = {"en": told} if isinstance(told, str) else told
        title = add(record["title"], "en", f"{gid}-head", teacher, pace, listed=not told)   # a narration names its topic
        if told.get("de"):
            explain[gid] = [add(explanation_speech(told["de"]), "de", None, teacher, pace, timed=True)]
            if told.get("en"):
                explain_en[gid] = [add(explanation_speech(told["en"], True), "marked", None, teacher, pace, False, True)]
        elif told.get("en"):
            explain[gid] = [add(explanation_speech(told["en"], True), "marked", None, teacher, pace, timed=True)]
        else:
            explain[gid] = [title] + [add(text, "en", None, teacher, pace) for text in
                                      [record["meaning"], "How it works: " + record["rule"]]
                                      + [pattern["label"] + ": " + pattern["form"] for pattern in record["patterns"]]
                                      + (["Careful: " + record["contrast"]] if record.get("contrast") else [])]
        for index, example in enumerate(record["examples"]):
            add(example["de"], "de", f'{gid}-ex-{index}')
            add(example["en"], "en")

    add(names["redemittel"], "de")
    previous = None
    for record in lesson["redemittel"]:
        if record["group"] != previous:
            add(record["group"], "de")
            previous = record["group"]
        add(record["frame"], "de", f'{record["id"]}-head')
        add(record["gloss"], "en")
        add(record["when"] + ((". " + record["register"]) if record.get("register") else ""), "en")
        for index, variant in enumerate(record.get("variants", [])):
            add(variant["form"], "de", f'{record["id"]}-variant-{index}')
            add(variant["usage"], "en")
        for index, example in enumerate(record["examples"]):
            add(example["de"], "de", f'{record["id"]}-ex-{index}')
            add(example["en"], "en")

    story = lesson.get("story")
    if story:                                     # the closing story: read straight through, one clip per sentence
        add(names["story"], "de")
        add(story["title"], "de", "story-title")
        number = 0
        for paragraph in story["paragraphs"]:
            for sentence in story_sentences(paragraph["de"], language.profile(lesson.get("target_language", "de"))):
                number += 1
                add(sentence, "de", f"story-s{number}")
    return clips, sequence, controls, explain, explain_en


def lesson_plan(lesson, voices=None, narration=None):
    """build_plan plus what players need: title and section clips, story paragraphs, English example clips."""
    voices = voices_of(voices)
    clips, sequence, controls, explain, explain_en = build_plan(lesson, voices, narration)

    def add(text, kind="de"):
        clip = speech.make_clip(text, kind, voices)
        clips.setdefault(clip.clip_id, clip)
        return clip.clip_id

    plan = {"title": add(lesson["title"]),
            "sections": {key: add(name) for key, name in sections_of(lesson).items() if key != "story" or lesson.get("story")},
            "sequence": sequence, "controls": controls, "explain": explain, "explain_en": explain_en, "story": [],
            "english": {f'{record["id"]}-ex-{index}': add(example["en"], "en")
                        for section in ("vocabulary", "grammar", "redemittel") for record in lesson[section]
                        for index, example in enumerate(record["examples"])}}
    number = 0
    for paragraph in (lesson.get("story") or {}).get("paragraphs", []):
        ids = []
        for _sentence in story_sentences(paragraph["de"], language.profile(lesson.get("target_language", "de"))):
            number += 1
            ids.append(controls[f"story-s{number}"])
        plan["story"].append(ids)
    return clips, plan


# ---------------------------------------------------------------- listening orders ---
# Each step is [clip id, pause factor, id of the element to highlight, repeatable]. The pause before the next step
# grows with the factor and the clip's length, to about 2 s after an example (LISTEN_JS: after); a repeatable
# (German) step is played as often as the learner chose, with a shorter pause between the plays (again).
def listening_order(prefix, lesson, plan):
    """The whole lesson: vocabulary and expressions, grammar explained, then the story read through."""
    c, seq = plan["controls"], []
    seq += [[plan["title"], 0.3, None, 0], [plan["sections"]["vocabulary"], 0.3, None, 0]]
    for rec in lesson["vocabulary"]:
        seq.append([c[f'{rec["id"]}-head'], 0.6, prefix + rec["id"], 1])
        seq += [[c[f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1] for i in range(len(rec["examples"]))]
    if lesson["grammar"]:
        seq.append([plan["sections"]["grammar"], 0.3, None, 0])
    for rec in lesson["grammar"]:
        seq += [[cid, 0.4, prefix + rec["id"], 0] for cid in plan["explain"][rec["id"]]]
        seq += [[c[f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1] for i in range(len(rec["examples"]))]
    seq.append([plan["sections"]["redemittel"], 0.3, None, 0])
    for rec in lesson["redemittel"]:
        seq.append([c[f'{rec["id"]}-head'], 0.8, prefix + rec["id"], 1])
        seq += [[c[f'{rec["id"]}-variant-{i}'], 0.8, prefix + rec["id"], 1] for i in range(len(rec.get("variants", [])))]
        seq += [[c[f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1] for i in range(len(rec["examples"]))]
    if plan["story"]:
        seq.append([plan["sections"]["story"], 0.3, None, 0])
        seq += [[step[0], step[1], step[2], 0] for step in story_order(prefix, plan)]
    return seq


def examples_order(prefix, lesson, plan):
    """Only the example sentences, in reading order."""
    return [[plan["controls"][f'{rec["id"]}-ex-{i}'], 1.0, f'{prefix}{rec["id"]}-x{i}', 1]
            for section in ("vocabulary", "grammar", "redemittel") for rec in lesson[section]
            for i in range(len(rec["examples"]))]


def story_order(prefix, plan):
    """The story: title, then every sentence, with a longer breath at the end of each paragraph."""
    if not plan["story"]:
        return []
    seq, number = [[plan["controls"]["story-title"], 0.6, prefix + "story", 0]], 0
    for paragraph in plan["story"]:
        for index, cid in enumerate(paragraph):
            number += 1
            seq.append([cid, 0.9 if index == len(paragraph) - 1 else 0.25, f"{prefix}story-s{number}", 1])
    return seq


def number_examples(document, lesson):
    """Give every example an id (<card>-x<n>) so a listening session can highlight the sentence it plays."""
    for section, css in (("vocabulary", "voc"), ("grammar", "rule"), ("redemittel", "phrase")):
        for record in lesson[section]:
            def transform(block, rid=record["id"]):
                counter = iter(range(len(record["examples"]) + 1))
                return re.sub(r'<div class="ex">', lambda m: f'<div class="ex" id="{rid}-x{next(counter)}">', block)
            document = transform_card(document, css, record["id"], transform)
    return document


def inject_story_audio(document, plan, heads=None, ui=None):
    """Audio on each story sentence, a 🔊 per paragraph and, optionally, the headword clip on underlined words.
    `ui` translates the German button labels (language.ui_table)."""
    controls, tr = plan["controls"], (lambda text: esc((ui or {}).get(text, text)))
    document = re.sub(r'(<article class="story" id="story"><h3>.*?)(</h3>)', lambda m: m.group(1) + (
        f'<button type="button" class="story-play" aria-label="{tr("Ganze Geschichte anhören")}" title="{tr("Ganze Geschichte anhören")}">'
        f'{tr("🔊 Ganze Geschichte")}</button>') + m.group(2), document, count=1, flags=re.S)
    document = re.sub(r'<span class="ss" id="story-s(\d+)">',
                      lambda m: f'<span class="ss" id="story-s{m.group(1)}" data-audio="{controls["story-s" + m.group(1)]}">',
                      document)
    document = re.sub(r'(<div class="story-p" id="story-p\d+">)', lambda m: m.group(1) + (
        f'<button type="button" class="speak-button para-play" aria-label="{tr("Absatz anhören")}" title="{tr("Absatz anhören")}">🔊</button>'),
        document)
    if heads:
        document = re.sub(r'<span class="lw" data-card="([^"]+)"',
                          lambda m: m.group(0) + (f' data-h="{heads[m.group(1)]}"' if m.group(1) in heads else ""), document)
    return document


async def synthesize(clips, cache_dir, voices=None, concurrency=4):
    try:
        return await speech.synthesize(clips, cache_dir, voices_of(voices), concurrency)
    except speech.SpeechError as error:
        raise AudioError(str(error)) from error


def play_button(clip_id, label="Play audio"):
    return (f'<button type="button" class="speak-button" data-audio="{esc(clip_id)}" '
            f'aria-label="{esc(label)}" title="{esc(label)}">🔊</button>')


def transform_card(document, css_class, record_id, transform):
    opener = f'<article class="{css_class}" id="{esc(record_id)}">'
    start = document.find(opener)
    require(start >= 0, f"HTML is missing {css_class} card {record_id}")
    end = document.find("</article>", start)
    require(end >= 0, f"HTML card {record_id} is not closed")
    end += len("</article>")
    return document[:start] + transform(document[start:end]) + document[end:]


def inject_example_buttons(block, clip_ids, record_id, label="Play German example"):
    iterator = iter(clip_ids)
    count = 0

    def replacement(match):
        nonlocal count
        count += 1
        return match.group(0) + play_button(next(iterator), label)

    updated = re.sub(r'<div class="ex">', replacement, block)
    require(count == len(clip_ids),
            f"HTML/lesson example mismatch for {record_id}: HTML={count}, lesson={len(clip_ids)}")
    return updated


AUDIO_CSS = r"""
  .listen-row{display:flex;align-items:center;gap:9px;margin-top:13px;flex-wrap:wrap}
  .listen-open,.story-play,.speak-button{border:1px solid rgba(255,255,255,.28);color:#fff;background:rgba(15,23,42,.55);font:inherit;cursor:pointer;box-shadow:none}
  .listen-open{border-radius:999px;padding:8px 15px;font-size:14px;font-weight:700;min-height:38px}
  .story-play{border-radius:999px;padding:6px 13px;font-size:13.5px;font-weight:700;min-height:34px;white-space:nowrap}
  .speak-button{width:29px;height:29px;border-radius:50%;padding:0;display:inline-grid;place-items:center;font-size:14px;line-height:1;flex:0 0 auto;vertical-align:middle}
  .speak-button:hover,.listen-open:hover,.story-play:hover,.speak-button:focus-visible,.listen-open:focus-visible,.story-play:focus-visible{background:#394151;outline:2px solid #f2d36b;outline-offset:2px}
  .speak-button.is-playing,.listen-open.is-playing,.story-play.is-playing{background:#0f766e;border-color:#6ee7b7;animation:pulse 1.6s ease-in-out infinite}
  @keyframes pulse{50%{box-shadow:0 0 0 6px rgba(110,231,183,.18)}}
  .voc .top,.phrase .head,.rule h3,.story h3{align-items:center}
  .phrase .head,.rule h3,.story h3{display:flex;gap:8px;justify-content:space-between;flex-wrap:wrap}
  .ex>.speak-button,.story-p>.para-play{float:right;margin:-1px 0 4px 8px}
  .variant>.speak-button{margin-left:7px}
  .ss[data-audio]{cursor:pointer;border-radius:5px;transition:background .2s}
  .ss.is-playing,.ss.follow{background:rgba(242,211,107,.16);outline:none}
  .follow{outline:2px solid var(--yellow);outline-offset:3px;border-radius:10px}
  .lp{margin:12px 0 4px;padding:12px;border:1px solid rgba(255,255,255,.2);border-radius:14px;background:rgba(15,23,42,.72)}
  .lp-modes{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-bottom:10px}
  .lp-modes button{font:inherit;font-size:15px;font-weight:700;min-height:46px;border-radius:12px;cursor:pointer;color:#1a1030;background:var(--accent2);border:0}
  .lp-modes button[data-m="ex"]{background:#f2d36b}
  .lp-modes button[data-m="story"]{background:#6ee7b7}
  .lp-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:7px 0 0}
  .lp-row>span{flex:0 0 92px;font-size:12.5px;color:#dbe2ea;letter-spacing:.3px}
  .lp-row .chips{display:flex;gap:6px;flex-wrap:wrap}
  .lp-row .chips button{font:inherit;font-size:13.5px;min-height:34px;padding:4px 11px;border-radius:999px;cursor:pointer;color:#fff;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.22)}
  .lp-row .chips button[aria-pressed="true"]{background:#f2d36b;color:#1a1030;border-color:#f2d36b;font-weight:700}
  .lp-go{display:block;width:100%;margin:0 0 8px;font:inherit;font-size:15px;font-weight:700;min-height:46px;border-radius:12px;cursor:pointer;color:#064e3b;background:#ecfdf5;border:0}
  .now{position:fixed;left:50%;bottom:calc(14px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:30;display:flex;align-items:center;gap:8px;
       width:max-content;max-width:calc(100% - 24px);padding:6px 6px 6px 8px;border-radius:999px;background:#0f766e;color:#ecfdf5;box-shadow:0 8px 24px rgba(0,0,0,.45);font-size:14px}
  .now.paused{background:#334155}
  .now-c{display:flex;gap:5px;flex:none}
  .now-i{display:flex;flex-direction:column;min-width:0;line-height:1.25;padding:0 4px}
  .now-i b,.now-i small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .now-i small{font-size:12px;opacity:.85}
  .now button{font:inherit;font-size:14px;font-weight:700;border:0;border-radius:999px;padding:7px 13px;background:#ecfdf5;color:#064e3b;cursor:pointer;flex:none}
  .now-c button,.now button.x{width:40px;height:40px;padding:0;display:grid;place-items:center;background:rgba(255,255,255,.16);color:#ecfdf5}
  .now-c #now-p{background:#ecfdf5;color:#064e3b}
  .now button.x{width:36px;height:36px;font-size:16px}
  .now svg{width:20px;height:20px;fill:currentColor}
  .now button:focus-visible{outline:2px solid #f2d36b;outline-offset:2px}
  .tip{position:absolute;z-index:40;max-width:min(300px,calc(100% - 16px));padding:8px 11px;border-radius:10px;background:#0b1220;color:#f8fafc;
       border:1px solid #f2d36b;font-size:14px;box-shadow:0 8px 22px rgba(0,0,0,.45)}
  .lw{cursor:help}
  [hidden]{display:none !important}
  @media(max-width:520px){.speak-button{width:32px;height:32px}}
  @media(prefers-reduced-motion:reduce){.speak-button.is-playing,.listen-open.is-playing{animation:none}}
"""

LISTEN_HTML = """<div class="lp" id="lp" hidden data-unit="">
<button type="button" class="lp-go" id="lp-go" hidden></button>
<div class="lp-modes"><button type="button" data-m="all">▶ Ganze Lektion</button><button type="button" data-m="ex">▶ Nur Beispiele</button><button type="button" data-m="story">▶ Geschichte</button></div>
<div class="lp-row"><span>Jeder Satz</span><div class="chips" id="lp-each"></div></div>
<div class="lp-row"><span>Am Ende</span><div class="chips" id="lp-loop"></div></div>
<div class="lp-row"><span>🔊-Taste</span><div class="chips" id="lp-one"></div></div>
</div>
<div class="now" id="now" hidden><div class="now-c" id="now-c">
<button type="button" id="now-b" aria-label="Noch einmal" title="Noch einmal (am Satzanfang: zurück)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h2v14H6zm14 0v14L9 12z"/></svg></button>
<button type="button" id="now-p" aria-label="Pause" title="Pause"></button>
<button type="button" id="now-n" aria-label="Nächster Satz" title="Nächster Satz"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 5h2v14h-2zM4 5v14l11-7z"/></svg></button>
</div><span class="now-i"><b id="now-t"></b><small id="now-s"></small></span><button type="button" id="now-x">⏹ Stopp</button></div>
<div class="tip" id="tip" hidden></div>
"""

# The listening engine shared by the course app and single audio sheets. The host defines d (document),
# load/save (settings), need(id) (base64 audio, or '' while the page is still loading it), and the
# objects SEQ, EXS and STO: per unit, the steps of "Ganze Lektion", "Nur Beispiele" and "Geschichte".
# It runs in the host's scope, so its names must not repeat the host's (the app already has again(), end(), bar).
LISTEN_JS = r"""
  /* ---------------- listening: every run plays as one audio track, so it goes on with the screen off ---------------- */
  var A=load('listen',{one:0,each:2,loop:1});     /* one: plays per 🔊 tap (0 = until tapped again); each: plays of every German sentence in a session; loop: start again at the end */
  var AT=load('listen-at',{});                     /* per unit, where a stopped session goes on: {m: mode, i: step, n: steps, c: first clip} */
  var player=new Audio(), R=null, held=null, lastF=null, lock=null, tipT=null, unlocked=false;
  var RATE=22050, PCM={}, cached=0, SIL={}, decoder=null;      /* clips decoded once, and silences, as small WAV blobs */
  var SILENT='data:audio/wav;base64,UklGRiYAAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YQIAAAAAAA==';
  var lp=d.getElementById('lp'), lpGo=d.getElementById('lp-go'), tip=d.getElementById('tip'), nowBar=d.getElementById('now'), nowB=d.getElementById('now-b'),
      nowP=d.getElementById('now-p'), nowN=d.getElementById('now-n'), nowT=d.getElementById('now-t'), nowS=d.getElementById('now-s'), nowX=d.getElementById('now-x');
  var LABEL={all:'Ganze Lektion',ex:'Nur Beispiele',story:'Geschichte'};
  var ICON={play:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>',
            pause:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zm6.5 0H17v14h-3.5z"/></svg>'};
  /* the silence after a clip, in ms: a short breath before the same sentence again, a little more before the next one */
  function gapAgain(dur){ return 550+250*Math.min(dur,3.2); }          /* 0.8 s after a word, 1.35 s after a sentence */
  function gapNext(dur,f){ return 300+f*(gapAgain(dur)+400); }         /* f: the step's pause factor; 1.5–2 s after an example */
  function stepsOf(m){ return m==='ex'?EXS:m==='story'?STO:SEQ; }
  function mark(el,on){ if(el) el.classList.toggle('is-playing',on); }
  function follow(el,stay){ if(lastF) lastF.classList.remove('follow'); lastF=el||null; if(!el) return; el.classList.add('follow'); if(stay) return;
    var b=el.getBoundingClientRect(); if(b.top<90||b.bottom>innerHeight-90) el.scrollIntoView({block:'center',behavior:'smooth'}); }
  function wake(on){ try{ if(on&&!lock&&navigator.wakeLock) navigator.wakeLock.request('screen').then(function(l){ if(R) lock=l; else l.release(); },function(){});
    else if(!on&&lock){ lock.release(); lock=null; } }catch(e){} }
  function spot(it){ return typeof it[2]==='string'?d.getElementById(it[2]):it[2]; }
  /* reading along: in a written explanation (.say[data-clip]), the sentence being spoken lights up; .sn[data-at] says
     when it starts, in seconds into the clip (the mark's cut: what voiceOnly took off its start). The page scrolls with
     it only while the learner is following, that is while the sentence before was in view. */
  var SAY=null;
  function inView(el){ var b=el.getBoundingClientRect(); return b.bottom>60&&b.top<innerHeight-90; }
  function sayOff(){ if(SAY&&SAY.k>=0) SAY.s[SAY.k].classList.remove('lit'); SAY=null; }
  function readAlong(r,m,t){ var it=r.items[m.i], box=it&&m.cut!==undefined&&((r.o.btn&&r.o.btn.closest('article'))||spot(it)),
      el=box&&box.querySelector('.say[data-clip="'+it[0]+'"]');
    if(!el){ sayOff(); return; }
    if(!SAY||SAY.el!==el){ sayOff(); SAY={el:el,s:el.querySelectorAll('.sn[data-at]'),k:-1}; var fold=el.closest('details'); if(fold) fold.open=true; }
    var at=(t*RATE-m.at+m.cut)/RATE+0.1, k=-1;
    while(k+1<SAY.s.length&&+SAY.s[k+1].getAttribute('data-at')<=at) k++;
    if(k===SAY.k) return;
    var was=SAY.k>=0?SAY.s[SAY.k]:null, keep=was&&!d.hidden&&inView(was);
    if(was) was.classList.remove('lit'); SAY.k=k; if(k<0) return;
    SAY.s[k].classList.add('lit'); if(keep&&!inView(SAY.s[k])) SAY.s[k].scrollIntoView({block:'center',behavior:'smooth'}); }
  /* ---- a run's track: its clips, decoded once, joined with their pauses into one WAV that the phone plays like music ---- */
  function pageReady(){ return d.readyState!=='loading'?Promise.resolve():new Promise(function(ok){ d.addEventListener('DOMContentLoaded',function(){ ok(); },{once:true}); }); }
  function pcm(id){ if(PCM[id]!==undefined) return Promise.resolve(PCM[id]);
    var data=need(id); if(!data) return Promise.resolve(PCM[id]=null);
    var bin=atob(data), raw=new Uint8Array(bin.length); for(var i=0;i<bin.length;i++) raw[i]=bin.charCodeAt(i);
    if(!decoder){ var C=window.OfflineAudioContext||window.webkitOfflineAudioContext; decoder=new C(1,1,RATE); }
    return new Promise(function(ok){ decoder.decodeAudioData(raw.buffer,function(a){ var f=a.getChannelData(0), s=new Int16Array(f.length);
        for(var i=0;i<f.length;i++){ var v=f[i]; s[i]=v<=-1?-32768:v>=1?32767:v*32767; }
        var v=voiceOnly(s); cached+=v.length; ok(PCM[id]={b:new Blob([v]),n:v.length,cut:v.byteOffset/2}); },function(){ ok(PCM[id]=null); }); }); }
  /* a clip without the voice's own lead-in and tail (about a second at each join), so the pauses are what gapAgain and gapNext say */
  function voiceOnly(s){ var a=0, z=s.length-1; while(a<z&&Math.abs(s[a])<330) a++; while(z>a&&Math.abs(s[z])<330) z--;
    return z<=a?s:s.subarray(Math.max(0,a-Math.round(RATE*0.04)),Math.min(s.length,z+Math.round(RATE*0.1))); }
  function quiet(ms){ var n=Math.round(ms*RATE/1000); return SIL[n]||(SIL[n]={b:new Blob([new Int16Array(n)]),n:n}); }
  function decodeAll(list,k,fn){ var i=0, w=[]; function more(){ return i<list.length?fn(list[i++]).then(more):null; }
    for(var j=0;j<k;j++) w.push(more()); return Promise.all(w); }
  /* marks[k] = {i: step, at: its first sample, end: the sample after its last play}; an endless run is one round that loops */
  function track(r){ var items=r.items, n=items.length, each=r.o.each||1, laps=r.o.laps||0, rounds=laps||1, ids={};
    items.forEach(function(it){ ids[it[0]]=1; });
    return pageReady().then(function(){ return decodeAll(Object.keys(ids),4,pcm); }).then(function(){
      var parts=[], marks=[], at=0, lap, k, q;
      function add(p){ parts.push(p.b); at+=p.n; }
      for(lap=0;lap<rounds;lap++){
        for(k=0;k<n;k++){ var it=items[k], c=PCM[it[0]], reps=it[3]?each:1, m={i:k,at:at,end:at}; marks.push(m); if(!c) continue; m.cut=c.cut;
          var dur=c.n/RATE, last=laps&&lap===rounds-1&&k===n-1;                 /* a finite run ends right after its last sound */
          for(q=0;q<reps;q++){ add(c); m.end=at; if(q<reps-1) add(quiet(gapAgain(dur))); }
          if(!last) add(quiet(n>1?gapNext(dur,it[1]):gapAgain(dur))); }
        if(n>1&&!(laps&&lap===rounds-1)) add(quiet(1000)); }                    /* a breath before the next round */
      if(cached>RATE*1200){ PCM={}; cached=0; }                                  /* keep about 20 minutes decoded, no more */
      if(!at) return null;
      var h=new DataView(new ArrayBuffer(44));
      [[0,'RIFF'],[8,'WAVE'],[12,'fmt '],[36,'data']].forEach(function(w){ for(var i=0;i<4;i++) h.setUint8(w[0]+i,w[1].charCodeAt(i)); });
      h.setUint32(4,36+at*2,true); h.setUint32(16,16,true); h.setUint16(20,1,true); h.setUint16(22,1,true); h.setUint32(24,RATE,true);
      h.setUint32(28,RATE*2,true); h.setUint16(32,2,true); h.setUint16(34,16,true); h.setUint32(40,at*2,true);
      return {url:URL.createObjectURL(new Blob([h.buffer].concat(parts),{type:'audio/wav'})),marks:marks}; }); }
  function markAt(r,t){ var M=r.t.marks, s=t*RATE+2, lo=0, hi=M.length-1;
    while(lo<hi){ var mid=(lo+hi+1)>>1; if(M[mid].at<=s) lo=mid; else hi=mid-1; } return lo; }
  /* ---- playing a run ---- */
  function unlock(){ if(unlocked) return; unlocked=true; player.src=SILENT; var p=player.play();      /* a phone lets a page play later only after a tap */
    if(p) p.then(function(){ if(player.src===SILENT) player.pause(); },function(){}); }
  function go(){ var p=player.play(); if(p) p.catch(function(e){ var r=R; if(e&&e.name==='NotAllowedError'&&r){ r.paused=true; mark(r.o.btn,false); showBar(); } }); }
  function clip(id){ var data=need(id); if(!data) return false; player.loop=false; player.src='data:audio/mpeg;base64,'+data; go(); return true; }
  function attach(r,play){ player.loop=!r.o.laps; player.src=r.t.url; r.last=r.pos;
    player.onloadedmetadata=function(){ player.onloadedmetadata=null; if(R!==r) return; player.currentTime=r.pos; if(play&&!r.paused) go(); }; }
  function prepare(r,from){ r.ready=false; r.from=from; showBar();
    track(r).then(function(t){ if(R!==r&&held!==r){ if(t) URL.revokeObjectURL(t.url); return; }
      if(!t){ if(R===r) endRun(); return; }
      var old=r.t, k=0; while(k<t.marks.length-1&&t.marks[k].i<from) k++;
      r.t=t; r.pos=t.marks[k].at/RATE; r.cur=t.marks[k].i; r.ready=true;
      if(R===r){ if(r.o.follow) follow(spot(r.items[r.cur])); attach(r,true); showBar(); } if(old) URL.revokeObjectURL(old.url); }); }
  function remember(r,t){ var m=r.t.marks[markAt(r,t)], i=m.i+(t*RATE>=m.end&&m.end>m.at?1:0);
    if(i>0&&i<r.items.length) AT[r.o.unit]={m:r.o.mode,i:i,n:r.items.length,c:r.items[0][0]}; }
  function drop(r){ var live=R===r&&r.ready&&player.src===r.t.url, t=live?player.currentTime:(r.pos||0); if(R===r) sayOff();
    if(R===r){ player.pause(); player.removeAttribute('src'); try{ player.load(); }catch(e){} }
    mark(r.o.btn,false); if(r.o.btn&&r.o.btn.getAttribute('data-l')){ r.o.btn.textContent=r.o.btn.getAttribute('data-l'); r.o.btn.removeAttribute('data-l'); }
    if(r.o.mode){ if(r.done) delete AT[r.o.unit]; else if(r.ready) remember(r,t); save('listen-at',AT); }
    if(r.t) URL.revokeObjectURL(r.t.url); r.t=null; r.ready=false; }
  function stopAll(){ if(R) drop(R); if(held) drop(held); R=held=null; follow(null); wake(false); if(nowBar) nowBar.hidden=true; }
  /* items: [clip id, pause factor, element (or its id) to highlight, repeatable]; o: {btn, each, laps (0 = endless), follow, stop, label},
     and for a session from the panel also unit, mode and at (its first step) */
  function run(items,o){ if(!items||!items.length) return;
    if(!o.mode&&(held||R&&R.o.mode)){                      /* a 🔊 tap during a session holds the session: it waits in the bar, paused */
      if(R&&R.o.mode){ held=R; if(held.ready&&player.src===held.t.url) held.pos=player.currentTime; held.paused=true; player.pause(); mark(held.o.btn,false); }
      else if(R) drop(R); }
    else stopAll();
    var r=R={items:items,o:o,cur:-1,from:Math.min(o.at||0,items.length-1),lap:1,paused:false,ready:false};
    if(o.mode&&AT[o.unit]){ delete AT[o.unit]; save('listen-at',AT); }
    mark(o.btn,true); if(o.btn&&o.stop){ o.btn.setAttribute('data-l',o.btn.textContent); o.btn.textContent=o.stop; }
    media(r); if(items.length>1||!o.laps) wake(true); prepare(r,r.from); }
  function endRun(){ var r=R; if(!r) return;
    if(!r.o.mode&&held){ drop(r); R=held; held=null; R.paused=true; follow(R.cur>=0?spot(R.items[R.cur]):null,true); wake(false); media(R);
      if(R.ready) attach(R,false); showBar(); return; }                         /* back to the held session, paused */
    stopAll(); }
  function showBar(){ var r=R; if(!nowBar||!r) return; var n=r.items.length, many=n>1, s=[], icon=r.paused?'play':'pause';
    nowBar.hidden=false; nowBar.classList.toggle('paused',!!r.paused); nowB.hidden=nowN.hidden=!many;
    if(nowP.getAttribute('data-s')!==icon){ nowP.setAttribute('data-s',icon); nowP.innerHTML=ICON[icon];
      nowP.setAttribute('aria-label',r.paused?'Weiter':'Pause'); nowP.title=r.paused?'Weiter':'Pause'; }
    if(many) s.push((r.cur<0?r.from:r.cur)+1+' / '+n);
    if(!r.ready) s.push('wird vorbereitet …');
    else{ if(many&&(r.o.each||1)>1) s.push('je '+r.o.each+'×');
      if(r.o.laps!==1) s.push(r.o.laps?(r.lap+' / '+r.o.laps):(many?'⟳ Runde '+r.lap:'⟳ '+r.lap+'×')); }
    nowT.textContent=r.o.label||'Wiedergabe'; nowS.textContent=s.join(' · ');
    nowX.textContent=many?'✕':'⏹ Stopp'; nowX.classList.toggle('x',many); nowX.setAttribute('aria-label',many?'Beenden':'Stopp'); }
  function pauseOrPlay(){ var r=R; if(!r) return;
    if(!r.paused){ r.paused=true; player.pause(); mark(r.o.btn,false); wake(false); showBar(); return; }
    r.paused=false; mark(r.o.btn,true); wake(true); showBar();
    if(r.ready){ if(player.src===r.t.url) go(); else attach(r,true); } }
  function skip(n){ var r=R; if(!r||!r.ready||player.src!==r.t.url||r.items.length<2) return;   /* ⏭ the next sentence now; ⏮ this one again, or right at its start the one before */
    var M=r.t.marks, t=player.currentTime, k=markAt(r,t), m=M[k], j=n>0?k+1:(t-m.at/RATE>1.5||t*RATE>=m.end)?k:k-1;
    if(j>=M.length){ if(r.o.laps){ r.done=true; endRun(); return; } j=0; r.lap++; }
    j=Math.max(j,0); r.last=M[j].at/RATE; r.cur=M[j].i; player.currentTime=r.last; r.paused=false; mark(r.o.btn,true); if(r.o.follow) follow(spot(r.items[r.cur])); wake(true); showBar(); go(); }
  /* the lock screen and headphone buttons: ⏯ always, ⏮ ⏭ for a run of several sentences */
  function media(r){ var M=navigator.mediaSession; if(!M) return; var many=r.items.length>1,
      box=(r.o.btn&&r.o.btn.closest('.unit'))||(r.o.unit&&d.getElementById(r.o.unit))||d, h=box.querySelector('h1');
    try{ M.metadata=new MediaMetadata({title:(r.o.label||'Wiedergabe')+(h?' · '+h.textContent.trim():''),artist:d.title}); }catch(e){}
    try{ M.setActionHandler('previoustrack',many?function(){ skip(-1); }:null); M.setActionHandler('nexttrack',many?function(){ skip(1); }:null); }catch(e){} }
  if(navigator.mediaSession) [['play',function(){ if(R&&R.paused) pauseOrPlay(); }],['pause',function(){ if(R&&!R.paused) pauseOrPlay(); }],['stop',function(){ stopAll(); }]]
    .forEach(function(h){ try{ navigator.mediaSession.setActionHandler(h[0],h[1]); }catch(e){} });
  player.addEventListener('timeupdate',function(){ var r=R; if(!r||!r.ready||player.src!==r.t.url) return;
    var t=player.currentTime, k=markAt(r,t), m=r.t.marks[k], lap=r.lap;
    readAlong(r,m,t);
    if(r.o.laps) r.lap=Math.floor(k/r.items.length)+1; else if(t+1<r.last) r.lap++;            /* an endless run counts its rounds */
    r.last=t; if(m.i===r.cur){ if(lap!==r.lap) showBar(); return; }
    r.cur=m.i; if(r.o.follow) follow(spot(r.items[m.i])); showBar();
    if(r.o.mode){ remember(r,t); save('listen-at',AT); } });                                  /* even if the phone closes the page */
  player.addEventListener('ended',function(){ var r=R; if(r&&r.ready&&player.src===r.t.url){ r.done=true; endRun(); } });
  player.addEventListener('pause',function(){ var r=R; if(!r||r.paused||!r.ready||player.src!==r.t.url||player.ended) return;
    r.paused=true; mark(r.o.btn,false); wake(false); showBar(); });                           /* paused from outside (a call, another app) */
  player.addEventListener('play',function(){ var r=R; if(r&&r.paused&&r.ready&&player.src===r.t.url){ r.paused=false; mark(r.o.btn,true); showBar(); } });
  /* ---- the panel ---- */
  function chipRow(id,items,value,set){ var box=d.getElementById(id); box.innerHTML='';
    items.forEach(function(it){ var b=d.createElement('button'); b.type='button'; b.textContent=it[1]; b.setAttribute('aria-pressed',String(it[0]===value));
      b.addEventListener('click',function(){ set(it[0]); save('listen',A); liveSettings(); panel(); }); box.appendChild(b); }); }
  function liveSettings(){ [R,held].forEach(function(r){ if(!r||!r.o.mode||r.o.each===A.each&&r.o.laps===(A.loop?0:1)) return;
      var t=R===r&&r.ready&&player.src===r.t.url?player.currentTime:(r.pos||0), from=r.ready?r.t.marks[markAt(r,t)].i:r.from;
      r.o.each=A.each; r.o.laps=A.loop?0:1; prepare(r,from); });              /* a running session follows the panel from its current sentence */
    showBar(); }
  function panel(){ chipRow('lp-each',[[1,'1×'],[2,'2×'],[3,'3×'],[5,'5×']],A.each,function(v){A.each=v;});
    chipRow('lp-loop',[[0,'Einmal'],[1,'⟳ Endlos']],A.loop,function(v){A.loop=v;});
    chipRow('lp-one',[[1,'1×'],[3,'3×'],[0,'∞ bis Stopp']],A.one,function(v){A.one=v;});
    var u=lp.getAttribute('data-unit'), at=AT[u], steps=at&&stepsOf(at.m)[u], busy=[R,held].some(function(r){ return r&&r.o.mode&&r.o.unit===u; });
    lp.querySelector('[data-m="story"]').hidden=!(STO[u]&&STO[u].length);
    lpGo.hidden=busy||!(steps&&steps.length===at.n&&steps[0][0]===at.c&&at.i>0&&at.i<steps.length);    /* a stopped session goes on where it stopped */
    if(!lpGo.hidden) lpGo.textContent='▶ Weiter: '+LABEL[at.m]+' · '+(at.i+1)+' / '+steps.length; }
  function openPanel(btn){ var u=btn.getAttribute('data-unit'), row=btn.closest('.listen-row');
    if(!lp.hidden&&lp.getAttribute('data-unit')===u){ lp.hidden=true; return; }
    row.parentNode.insertBefore(lp,row.nextSibling); lp.setAttribute('data-unit',u); lp.hidden=false; panel(); }
  function session(u,m,at){ lp.hidden=true;
    run(stepsOf(m)[u],{btn:d.querySelector('.listen-open[data-unit="'+u+'"]'),each:A.each,laps:A.loop?0:1,follow:true,label:LABEL[m],unit:u,mode:m,at:at||0}); }
  function gloss(w){ var t=w.getAttribute('title')||w.getAttribute('data-t'); if(!t||!tip) return;
    if(w.getAttribute('title')){ w.setAttribute('data-t',t); w.removeAttribute('title'); }      /* no native tooltip on top of ours */
    tip.textContent=t; tip.hidden=false; var b=w.getBoundingClientRect();
    tip.style.left=Math.max(8,Math.min(b.left+scrollX,scrollX+innerWidth-tip.offsetWidth-8))+'px'; tip.style.top=(b.bottom+scrollY+6)+'px';
    clearTimeout(tipT); tipT=setTimeout(function(){ tip.hidden=true; },3200);
    var h=w.getAttribute('data-h'); if(h) run([[h,0.4,null,0]],{laps:1,label:'Wort'}); }
  d.addEventListener('click',unlock,true);
  lp.addEventListener('click',function(e){ var u=lp.getAttribute('data-unit'), b=e.target.closest('[data-m]');
    if(b) session(u,b.getAttribute('data-m')); else if(e.target.closest('#lp-go')&&AT[u]) session(u,AT[u].m,AT[u].i); });
  nowB.addEventListener('click',function(){ skip(-1); });
  nowN.addEventListener('click',function(){ skip(1); });
  nowP.addEventListener('click',pauseOrPlay); nowX.addEventListener('click',endRun);
  d.addEventListener('click',function(e){
    var b=e.target.closest('.speak-button,.explain-button,.listen-open,.story-play,.ss[data-audio],.lw'); if(!b) return;
    if(b.classList.contains('lw')){ gloss(b); return; }
    e.stopPropagation();
    if(b.classList.contains('listen-open')){ openPanel(b); return; }        /* also during a session: its settings apply at once */
    if(R&&R.o.btn===b){ endRun(); return; }
    if(b.classList.contains('story-play')){ var u=b.closest('.unit')?b.closest('.unit').id:'L'; run(STO[u],{btn:b,each:1,laps:A.one,follow:true,stop:'⏹ Stopp',label:'Geschichte'}); return; }
    if(b.classList.contains('explain-button')){ run(b.getAttribute('data-chain').split(' ').map(function(id){ return [id,0.4,null,0]; }),{btn:b,laps:1,label:'Erklärung'}); return; }
    if(b.classList.contains('para-play')){ run([].map.call(b.closest('.story-p').querySelectorAll('.ss[data-audio]'),function(s){ return [s.getAttribute('data-audio'),0.3,s,0]; }),
      {btn:b,laps:A.one,follow:true,label:'Absatz'}); return; }
    var sentence=b.classList.contains('ss');
    run([[b.getAttribute('data-audio'),0.8,sentence?b:null,0]],{btn:b,laps:A.one,follow:sentence,label:sentence?'Satz':'Wiederholen'});
  },true);
"""

AUDIO_JS = r"""
<script>
(function(){
  'use strict';
  var d=document, P=__PAYLOADS__, SEQ={L:__SEQUENCE__}, EXS={L:__EXAMPLES__}, STO={L:__STORY__};
  function load(k,dflt){ try{ var v=localStorage.getItem('study-sheet:'+k); return v?JSON.parse(v):dflt; }catch(e){ return dflt; } }
  function save(k,v){ try{ localStorage.setItem('study-sheet:'+k,JSON.stringify(v)); }catch(e){} }
  function need(id){ return P[id]||''; }
__LISTEN__
})();
</script>
"""


def inject_audio(document, lesson, payloads, plan):
    require('<meta name="study-pack-audio"' not in document, "Input already contains embedded audio")
    require(document.count("<h2") in (3, 4), "Input must contain the three teaching sections and at most a story")
    controls, prof = plan["controls"], language.profile(lesson.get("target_language", "de"))
    ui, name = language.ui_table(prof), prof["name"]

    document = document.replace(
        '<meta name="study-pack-status"',
        '<meta name="study-pack-audio" content="embedded">\n<meta name="study-pack-status"', 1)
    require("</style>" in document, "HTML has no style block")
    document = document.replace("</style>", AUDIO_CSS + "\n</style>", 1)
    open_button = ('<div class="listen-row"><button type="button" class="listen-open" data-unit="L">'
                   f'{esc(ui.get("🎧 Anhören", "🎧 Anhören"))}</button></div>')
    header_end = document.find("</header>")
    require(header_end >= 0, "HTML has no header")
    document = document[:header_end] + open_button + document[header_end:]
    document = document.replace("</header>", "</header>" + language.localize(LISTEN_HTML, ui), 1)

    for record in lesson["vocabulary"]:
        def transform(block, record=record):
            head_id = controls[f'{record["id"]}-head']
            block, count = re.subn(
                r'(<div class="top"><span class="de">.*?</span>)(?=<span class="en">)',
                lambda match: match.group(1) + play_button(head_id, f"Play {name} headword"),
                block, count=1, flags=re.S)
            require(count == 1, f"Cannot place headword audio for {record['id']}")
            ids = [controls[f'{record["id"]}-ex-{index}'] for index in range(len(record["examples"]))]
            return inject_example_buttons(block, ids, record["id"])
        document = transform_card(document, "voc", record["id"], transform)

    for record in lesson["grammar"]:
        def transform(block, record=record):
            head_id = controls[f'{record["id"]}-head']
            block, count = re.subn(
                r'(<h3>.*?</h3>)',
                lambda match: match.group(1)[:-5] + play_button(head_id, "Play grammar title") + "</h3>",
                block, count=1, flags=re.S)
            require(count == 1, f"Cannot place grammar-title audio for {record['id']}")
            ids = [controls[f'{record["id"]}-ex-{index}'] for index in range(len(record["examples"]))]
            return inject_example_buttons(block, ids, record["id"])
        document = transform_card(document, "rule", record["id"], transform)

    for record in lesson["redemittel"]:
        def transform(block, record=record):
            head_id = controls[f'{record["id"]}-head']
            block, count = re.subn(
                r'(<div class="head">.*?</div>)',
                lambda match: match.group(1)[:-6] + play_button(head_id, f"Play {name} expression") + "</div>",
                block, count=1, flags=re.S)
            require(count == 1, f"Cannot place expression audio for {record['id']}")
            variant_ids = iter(controls[f'{record["id"]}-variant-{index}']
                               for index in range(len(record.get("variants", []))))
            seen = 0
            def variant_replacement(match):
                nonlocal seen
                seen += 1
                return match.group(1) + play_button(next(variant_ids), f"Play {name} variant") + "</p>"
            block = re.sub(r'(<p class="variant">.*?)(</p>)', variant_replacement, block, flags=re.S)
            require(seen == len(record.get("variants", [])),
                    f"HTML/lesson variant mismatch for {record['id']}")
            ids = [controls[f'{record["id"]}-ex-{index}'] for index in range(len(record["examples"]))]
            return inject_example_buttons(block, ids, record["id"])
        document = transform_card(document, "phrase", record["id"], transform)

    document = number_examples(document, lesson)
    heads = {record["id"]: controls[f'{record["id"]}-head'] for record in lesson["vocabulary"] + lesson["redemittel"]}
    document = inject_story_audio(document, plan, heads, ui)
    compact = lambda value: json.dumps(value, separators=(",", ":"))
    script = (AUDIO_JS.replace("__LISTEN__", language.localize(LISTEN_JS, ui))
              .replace("__SEQUENCE__", compact(listening_order("", lesson, plan)))
              .replace("__EXAMPLES__", compact(examples_order("", lesson, plan)))
              .replace("__STORY__", compact(story_order("", plan)))
              .replace("__PAYLOADS__", compact(payloads)))
    require("</body>" in document, "HTML has no body end tag")
    return document.replace("</body>", script + "\n</body>", 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--voice-de", help="voice for the target language (default: the language profile's voice)")
    parser.add_argument("--voice-en", default=speech.DEFAULT_VOICES["en"], help="English voice for glosses and explanations")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--confirm-external-tts", action="store_true",
                        help="Confirm that selected lesson text may be sent to the Edge TTS service")
    args = parser.parse_args(argv)
    try:
        require(args.confirm_external_tts,
                "Hosted synthesis sends selected lesson text externally; obtain approval and pass --confirm-external-tts")
        require(args.input.resolve() != args.output.resolve(), "Never overwrite the input HTML")
        require(not args.output.exists(), "Output exists; choose a new test/version filename")
        require(args.output.suffix.lower() == ".html", "Output must be an HTML file")
        require(args.output.parent.is_dir(), "Output directory does not exist")
        require(1 <= args.concurrency <= 8, "Concurrency must be from 1 to 8")
        lesson = json.loads(args.lesson.read_text(encoding="utf-8"))
        require(isinstance(lesson, dict) and lesson.get("target_language"), "Lesson must be v2 lesson data")
        prof = language.profile(lesson["target_language"])
        speech.use(prof)
        for key in ("title", "vocabulary", "grammar", "redemittel"):
            require(key in lesson, f"Lesson is missing {key}")
        voices = {"de": args.voice_de or prof["voice"], "en": args.voice_en, **language.narrator(prof)}
        clips, plan = lesson_plan(lesson, voices)
        print(f"AUDIO PLAN: {len(clips)} unique clips; {len(plan['sequence'])} listening steps; voices={voices}")
        paths = asyncio.run(synthesize(clips, args.cache_dir, voices, args.concurrency))
        payloads = {}
        for clip_id, path in paths.items():
            data = path.read_bytes()
            require(len(data) > 256, f"Audio clip is empty: {path}")
            payloads[clip_id] = base64.b64encode(data).decode("ascii")
        source = args.input.read_text(encoding="utf-8")
        output = inject_audio(source, lesson, payloads, plan)
        require("http://" not in output and "https://" not in output,
                "Output unexpectedly contains an external URL")
        require(output.count("data:audio/mpeg;base64,") == 1,
                "Embedded audio payload bank was not created exactly once")
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(output)
        print(f"WROTE: {args.output} ({args.output.stat().st_size} bytes, fully embedded audio)")
        return 0
    except (AudioError, speech.SpeechError, language.LanguageError, OSError, json.JSONDecodeError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
