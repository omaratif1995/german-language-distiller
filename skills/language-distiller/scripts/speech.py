#!/usr/bin/env python3
"""Language-aware speech for German study material: German is always spoken by a German voice.

Why: Microsoft's multilingual neural voices guess the language of each request, and the Edge
service marks every request as en-US. Short German words ("rund", "total", "als") then come out
with English pronunciation. This module splits each clip into German and English segments,
speaks every segment with a single-language voice, and joins the MP3 segments into one clip.

Text kinds:
  "de"      German text (headwords, examples, phrases): one German segment, never split.
  "en"      English text (glosses, cues, explanations): German words inside it are detected
            and spoken by the German voice.
  "mix-de"  German-based notes with English parts (forms lines such as "abschließen = to complete").
  "marked"  Authored narration: German words are marked explicitly with «…»; nothing is guessed.

Detection uses word lists plus the German and English `pyspellchecker` dictionaries. They are required
whenever unmarked mixed text is split, so the same text gives the same clips on every machine.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import language

DEFAULT_VOICES = {"de": "de-DE-KatjaNeural", "en": "en-US-AvaNeural"}   # target language ("de" slot), gloss language
TRIES, RETRY_SECONDS = 4, 1.0            # a failed voice request is sent again after 1, 2 and 3 seconds


class SpeechError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SpeechError(message)


# ------------------------------------------------------------------ speakable text ---
_COMMON = (("…", ", "), ("...", ", "), ("„", ""), ("“", ""), ("”", ""), ("‚", ""), ("‘", ""), ("’", "'"),
           ("«", ""), ("»", ""), ("(!)", ""), ("~", ""), ("*", ""), (" | ", ", "), ("·", ". "), (" = ", ": "))
_EN = (("→", " becomes "), ("↔", ", the opposite of "), ("≈", ", roughly "), (" + ", " plus "), (" / ", " or "),
       ("e.g.", "for example"), ("i.e.", "that is"), ("etc.", "and so on"), (" vs ", " versus "),
       (" sb ", " somebody "), (" sth ", " something "), ("sb.", "somebody"), ("sth.", "something"),
       ("Akk.", "accusative"), ("Dat.", "dative"), ("Gen.", "genitive"), ("Nom.", "nominative"))


def speakable(text, lang="de"):
    """Turn visual notation into text a voice reads naturally."""
    text = " " + str(text).strip() + " "
    for old, new in _COMMON + (_DE if lang == "de" else _EN):
        text = text.replace(old, new)
    text = re.sub(r"\((e|n|en|s|es|er)\)", r"\1", text)          # Tag(e)s → Tages
    text = re.sub(rf"(?<![{_LETTERS}])'|'(?![{_LETTERS}])", "", text)   # quote marks, not don't / I'm
    text = re.sub(rf"(?<![\w])-(?=[{_LOWER}])", "", text)          # endings -er, -en → er, en
    text = re.sub(r"[()\[\]{}]", ", ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([.!?])(?:\s*[,;:.])+", r"\1", text)          # "Gehälter. ," / "CV.." / "wann?."
    text = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)
    text = re.sub(r"[,;:]+\s*([.!?])", r"\1", text)
    ends_sentence = text.rstrip()[-1:] in ".!?"
    text = text.strip(" ,;:.")
    return text + "." if ends_sentence and text and text[-1] not in "!?" else text


# ------------------------------------------------------------------ language detection ---
# What the splitter knows about the target language comes from its profile (languages/<code>.json, see use()):
# its common words, the words it shares with English, its articles, its letters and how its notation is read aloud.
# The slot names stay "de" (the target language) and "en" (the gloss language) for every language.
EN_WORDS = set("""
the a an of to in on at for with and or but is are was were be been being it its this that these those you your we
they he she them his her our their not no yes if then when where what which who whom how why because so as than
after before only also just very more most some any all each every one two three first second use used uses using
say says said mean means meaning rule rules important verb verbs noun nouns clause clauses main subordinate end
forms ending endings article articles adjective adjectives plural singular case cases subject object
example examples like same different word words sentence sentences here there can could would should must will have
has had do does did make makes goes go comes come stands stand takes take need needs something someone somebody
about into from by up out over while since until though although both either neither other another often always
never usually sometimes too still already yet now today watch out listen look let's lets here's that's it's you'll
don't doesn't isn't can't won't means tells tell show shows think thing things way ways time times part parts
i i'm i've i'd i'll english german germany ok okay monday tuesday wednesday thursday friday saturday sunday
sb sth programme programmes mr mrs ms sir madam km umlaut umlauts plurals adverb adverbs preposition
prepositions pronoun pronouns conjunction conjunctions connector connectors infinitive infinitives participle
prefix prefixes suffix suffixes stem tense present past future masculine feminine neuter dative accusative
genitive nominative rare
""".split())
_BOUNDARY = re.compile(r"[.:;!?()=·|→\[\]]")
_REGION = re.compile(r"(^|[·(;|,]\s*)(A\s*/\s*CH|CH|A|D\s*\(south\)|D)(?=\s*(?:also\s*)?:)")
_REGIONS = {"A/CH": "in Österreich und in der Schweiz", "CH": "in der Schweiz", "A": "in Österreich",
            "D(south)": "in Süddeutschland", "D": "in Deutschland"}
_dictionaries = None


def use(prof):
    """Split and speak text for the target language of this profile (language.profile); German until called."""
    global DE_WORDS, AMBIGUOUS, ARTICLES, _DE, _LONE, _SPELL, _GERMAN_NOTATION, _LETTERS, _UPPER, _LOWER
    global _SPECIAL, _TOKEN, _dictionaries
    s = prof["speech"]
    DE_WORDS, AMBIGUOUS, ARTICLES = (set(s[key].lower().split()) for key in ("words", "ambiguous", "articles"))
    _DE = tuple(tuple(pair) for pair in s["speakable"])
    _LONE, _SPELL, _GERMAN_NOTATION = set(s.get("lone", [])), s.get("spellchecker"), bool(s.get("german_notation"))
    _LETTERS, _UPPER, _LOWER = s["letters"], s["upper"], s["lower"]
    _SPECIAL = re.compile(f"[{s['special']}]") if s.get("special") else None
    _TOKEN = re.compile(rf"(?:(?<![{_LETTERS}])-)?[{_LETTERS}]+(?:['’][{_LETTERS}]+)*")
    _dictionaries = None


use(language.profile("de"))


def normalize(text):
    """Notation to settle before detection: regional labels (A:, CH:, D:), optional letters, stress capitals."""
    text = str(text)
    if _GERMAN_NOTATION:
        text = _REGION.sub(lambda m: m.group(1) + _REGIONS[re.sub(r"\s+", "", m.group(2))], text)
        text = re.sub(r"(Österreich|Schweiz|[Dd]eutschland) also:", r"\1 auch:", text)
        text = re.sub(r"\b(Konjunktiv|Partizip) (II|I)\b", lambda m: m.group(1) + (" zwei" if m.group(2) == "II" else " eins"), text)
        text = re.sub(rf"(?<=[{_LETTERS}])\((e|n|en|s|es|er)\)(?=[{_LOWER}])", r"\1", text)      # schütt(e)le
    return re.sub(rf"\b[{_LOWER}]+[{_UPPER}]{{2,}}[{_LOWER}]*\b", lambda m: m.group(0).lower(), text)  # unterBRECHEN


def dictionaries_available():
    try:
        import spellchecker  # noqa: F401
        return True
    except ImportError:
        return False


def _dicts():
    global _dictionaries
    if _dictionaries is None:
        try:
            from spellchecker import SpellChecker
        except ImportError as error:
            raise SpeechError("pyspellchecker is required to find target-language words inside English text: "
                              "pip install pyspellchecker") from error
        _dictionaries = (SpellChecker(language=_SPELL) if _SPELL else None, SpellChecker(language="en"))
    return _dictionaries


def _classify(token, sentence_start, base, notes=False):
    word = token.lstrip("-")
    low = word.lower()
    if token.startswith("-"):
        return "de"                                   # German endings such as -er, -ung
    if _SPECIAL and _SPECIAL.search(word):
        return "de"                                   # letters only the target language has: ä, ñ
    if low in AMBIGUOUS:
        return "?"
    in_de, in_en = low in DE_WORDS, low in EN_WORDS
    if in_de != in_en:
        return "de" if in_de else "en"
    if in_de or len(word) == 1 or re.fullmatch(r"[IVX]+", word):
        return "?"                                    # in both lists, single letters, Roman numerals
    if re.fullmatch(rf"[{_UPPER}]{{2,}}s?", word):
        return base                                   # acronyms (CV, TV, PCs) follow the surrounding text
    capital = word[:1].isupper() and not sentence_start
    de, en = _dicts()
    if de is None:                                    # no dictionary for this language: only the lists decide
        return "en" if en.known([low]) else ("de" if capital else base)
    known_de, known_en = bool(de.known([low])), bool(en.known([low]))
    if known_de != known_en:
        return "de" if known_de else "en"
    if not known_de:
        return "de" if capital else base              # unknown capitalized word: a German name or noun
    ratio = (de[low] / de.word_frequency.total_words) / max(en[low] / en.word_frequency.total_words, 1e-12)
    if ratio > 8:
        return "de"                                   # far more common in German: essen, hin
    if base == "de" or notes:                         # German notes: capitals are nouns, cognates need context
        return "de" if capital else "?"
    return "en" if ratio < 1 / 8 else "?"


def _gloss_spans(text):
    """In German notes, the side right of '=' is an English gloss: «abschließen = to complete»."""
    spans = []
    for part in re.finditer(r"[^·|;]+", text):
        left, equals, right = part.group(0).partition("=")
        if equals and left.strip() and right.strip():
            spans.append((part.start() + len(left) + 1, part.end()))
    return spans


def segments(text, base="en"):
    """Split text into [(lang, text)] runs. «…» marks German explicitly; otherwise words are classified."""
    text = str(text)
    if "«" in text:
        out = [("de" if i % 2 else base, part) for i, part in enumerate(re.split(r"[«»]", text)) if part]
        return _merge(out)
    tokens = list(_TOKEN.finditer(text))
    if not tokens:
        return [(base, text)] if text.strip() else []
    _dicts()                                          # fail early, not only for words outside the lists
    glosses = _gloss_spans(text) if base == "de" else []
    labels, clauses, groups, bases, clause, previous_end = [], [], [], [], 0, 0
    for i, match in enumerate(tokens):
        gap = text[previous_end:match.start()]
        joined = i > 0 and gap == "-"                 # S-Bahn, E-Mail, dass-Satz: parts of one compound
        if not joined and _BOUNDARY.search(gap):
            clause += 1                               # neighbours vote only within their own clause
        clauses.append(clause)
        groups.append(groups[-1] if joined else i)
        bases.append("en" if any(a <= match.start() < b for a, b in glosses) else base)
        sentence_start = previous_end == 0 or bool(re.search(r"[.!?:]\s*$", gap))
        label = _classify(match.group(0), sentence_start, bases[-1], notes=base == "de")
        after = text[match.end():match.end() + 2]
        if after[:1] == "-" and not re.match(rf"-[{_LETTERS}]", after):
            label = "de"                              # prefix notation: be-, ver-, ent-
        elif re.search(r"(…|\.\.\.)$", gap):          # ending notation: am …sten, but English …ing
            label = "en" if match.group(0).lower() in ("ing", "ed", "ly") else "de"
            if label == "de" and labels and labels[-1] == "?":
                labels[-1] = "de"
        labels.append(label)
        previous_end = match.end()

    def members(group):
        return [j for j, g in enumerate(groups) if g == group]

    for group in sorted(set(groups)):                 # a compound speaks one language unless its parts disagree
        found = {labels[j] for j in members(group)} - {"?"}
        if len(found) == 1 and len(members(group)) > 1:
            for j in members(group):
                labels[j] = next(iter(found))
    for i in range(len(tokens) - 1):                  # article + capitalized word: die Babysitter, ein Sabbatical
        nxt = groups[i] + len(members(groups[i]))
        if (nxt < len(tokens) and tokens[i].group(0).lower() in ARTICLES and tokens[nxt].group(0)[:1].isupper()
                and clauses[nxt] == clauses[i] and not text[tokens[i].end():tokens[nxt].start()].strip()):
            for j in [i] + members(groups[nxt]):
                labels[j] = "de"
    for i, label in enumerate(labels):                # resolve ambiguous words from their neighbours
        if label != "?":
            continue
        left = [labels[j] for j in range(i - 1, -1, -1) if labels[j] != "?" and clauses[j] == clauses[i]][:3]
        right = [labels[j] for j in range(i + 1, len(labels)) if labels[j] != "?" and clauses[j] == clauses[i]][:3]
        weight = {"de": 0.0, "en": 0.0}               # the nearest neighbours count most
        for side in (left, right):
            for distance, lang in enumerate(side):
                weight[lang] += 1 / (distance + 1)
        if abs(weight["de"] - weight["en"]) > 1e-9:
            labels[i] = max(weight, key=weight.get)
        elif left or right:                           # a tie: a function word belongs to the phrase it opens
            labels[i] = right[0] if right else left[0]
        elif tokens[i].group(0).lower() in _LONE:
            labels[i] = "de"                          # a lone «die» is the German article
        elif text[tokens[i].end():].lstrip()[:1] == ":":
            later = [labels[j] for j in range(i + 1, len(labels)) if labels[j] != "?"][:1]
            labels[i] = (later or [bases[i]])[0]      # a label such as «also:» speaks like what it introduces
        else:
            labels[i] = bases[i]
    starts = [0]                                      # each word keeps the punctuation that follows it;
    for i in range(1, len(tokens)):                   # a number goes with the word after it (300 g Mehl)
        number = re.search(r"\d[\d.,:]*\s*$", text[tokens[i - 1].end():tokens[i].start()])
        starts.append(tokens[i - 1].end() + number.start() if number else tokens[i].start())
    starts.append(len(text))
    return _merge([(labels[i], text[starts[i]:starts[i + 1]]) for i in range(len(tokens))])


def unmarked_german(text):
    """Words in the unmarked (English) parts of a narration that look German: probably a missing «…»."""
    found = []
    for index, part in enumerate(re.split(r"[«»]", str(text))):
        if index % 2 == 0 and part.strip():
            found += [chunk.strip(" ,.;:!?()") for lang, chunk in segments(part, "en") if lang == "de"]
    return [word for word in found if word]


def _merge(parts):
    merged = []
    for lang, chunk in parts:
        if merged and (merged[-1][0] == lang or not re.search(rf"[{_LETTERS}0-9]", chunk)):
            merged[-1] = (merged[-1][0], merged[-1][1] + chunk)
        else:
            merged.append((lang, chunk))
    return [(lang, chunk) for lang, chunk in merged if chunk.strip()]


# ------------------------------------------------------------------ clips ---
@dataclass(frozen=True)
class Clip:
    clip_id: str
    parts: tuple            # ((lang, spoken text), ...)
    voices: tuple = field(default=())
    pauses: tuple = ()      # seconds of silence after each part but the last
    rate: str = ""          # speaking rate for the voice service ("-15%": a little slower), "" = normal
    timed: bool = False     # keep the time of every spoken word (clips/<id>.words.json), to read along

    @property
    def text(self):
        return " ".join(f"[{lang}] {spoken}" for lang, spoken in self.parts)


def _pause_after(chunk, after=""):
    """A join should sound like one speaker: a breath inside a sentence, a real pause after it. The punctuation can
    also open the next part («als», the verb …: the comma follows the German word)."""
    end, lead = chunk.rstrip(" «»\"'」』")[-1:], after.lstrip(" «»\"'「『")[:1]
    end = lead if lead and lead in ".!?。！？؟:;：；؛,–—、，،" else end
    return 0.45 if end in ".!?。！？؟" else 0.3 if end in ":;：；؛" else 0.2 if end in ",–—、，،" else 0.08


def make_clip(text, kind, voices, rate="", timed=False):
    """Build a clip for `text` of the given kind ("de", "en", "mix-de", "marked"), spoken by `voices` (one per
    language; the same voice for both makes one speaker) at `rate` ("-15%" is a little slower). A `timed` clip
    also keeps when each word is spoken (a written explanation lights up its sentences); the id stays the same."""
    require(kind in ("de", "en", "mix-de", "marked"), f"unknown text kind {kind}")
    if kind == "de":
        raw = [("de", normalize(text))]
    elif kind == "marked":
        raw = segments(text, base="en")
    else:
        raw = segments(normalize(text), base="de" if kind == "mix-de" else "en")
    spoken = [(lang, speakable(chunk, lang), _pause_after(chunk, raw[i + 1][1] if i + 1 < len(raw) else ""))
              for i, (lang, chunk) in enumerate(raw)]
    spoken = [item for item in spoken if re.search(rf"[{_LETTERS}0-9]", item[1])]
    require(spoken, f"empty audio text: {text!r}")
    parts = tuple((lang, words) for lang, words, _ in spoken)
    pauses = tuple(pause for _, _, pause in spoken[:-1])
    key = json.dumps([[voices[lang], words] for lang, words in parts] + ([list(pauses)] if pauses else [])
                     + ([rate] if rate else []), ensure_ascii=False)
    return Clip("a_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20], parts,
                tuple(sorted((lang, voices[lang]) for lang in {lang for lang, _ in parts})), pauses, rate, timed)


def segment_id(voice, spoken, rate=""):
    return "s_" + hashlib.sha256(f"{voice}\0{spoken}{chr(0) + rate if rate else ''}".encode("utf-8")).hexdigest()[:20]


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        found = shutil.which("ffmpeg")
        require(found, "ffmpeg is required: install ffmpeg or `pip install imageio-ffmpeg`")
        return found


_LEAD = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02"
_TRIM = f"{_LEAD},areverse,{_LEAD},areverse"
SAMPLE_RATE = 24000                 # the voice service's MP3s, and every clip joined from them


def _words_file(segment):
    return segment.with_suffix(".words.jsonl")      # the service's word timings, beside a segment's MP3


def _samples(path, ff, audio_filter=None):
    """How many samples an MP3 decodes to at SAMPLE_RATE, after an optional ffmpeg filter (_LEAD, _TRIM)."""
    command = [ff, "-hide_banner", "-loglevel", "error", "-i", str(path)] + (["-af", audio_filter] if audio_filter else [])
    command += ["-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    return len(subprocess.run(command, check=True, capture_output=True).stdout) // 2


def _boundaries(path):
    """[(seconds, word)] from the service's JSON lines (offsets in 100 ns)."""
    words = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        item = json.loads(line) if line.strip() else {}
        if item.get("type") == "WordBoundary":
            words.append((item["offset"] / 1e7, item["text"]))
    return words


def clip_words(item, paths, ff=None, measure=_samples):
    """When each word of a clip is spoken, [(seconds, word)]. One segment keeps the service's own timings. Joined
    segments (_join) lose their lead-in silence, and each starts after the trimmed parts and pauses before it."""
    marks = [_boundaries(_words_file(path)) for path in paths]
    if len(paths) == 1:
        return marks[0]
    words, start = [], 0.0
    for index, (path, own) in enumerate(zip(paths, marks)):
        lead = (measure(path, ff) - measure(path, ff, _LEAD)) / SAMPLE_RATE
        words += [(start + max(0.0, at - lead), word) for at, word in own]
        start += measure(path, ff, _TRIM) / SAMPLE_RATE + (item.pauses[index] if index < len(item.pauses) else 0.0)
    return words


def clip_timings(cache_dir, clip_id):
    """The word timings kept with a timed clip, [(seconds, word)], or [] when it has none."""
    path = Path(cache_dir) / "clips" / f"{clip_id}.words.json"
    return [(at, word) for at, word in json.loads(path.read_text(encoding="utf-8"))] if path.is_file() else []


def _communicate(edge_tts, text, voice, rate, marks):
    if marks:                       # edge-tts 7 reports sentences unless asked for words; older releases only words
        try:
            return edge_tts.Communicate(text=text, voice=voice, rate=rate, boundary="WordBoundary")
        except TypeError:
            pass
    return edge_tts.Communicate(text=text, voice=voice, rate=rate)


def _time_limit(spoken):
    """Seconds one voice request may take: a minute, and a second for every five characters, more than twice as long
    as saying them takes (speech runs at 10-12 characters a second; the service sends audio faster). edge-tts sets a
    read limit, but aiohttp drops it once the websocket is open, so without this a connection lost while the computer
    sleeps, or in a network change, waits forever."""
    return 60 + len(spoken) / 5


def _join(paths, pauses, target, ff):
    """Each TTS segment comes with up to a second of its own silence: trim it and join with measured pauses.
    The result keeps the service's format (24 kHz mono, 48 kbit/s CBR, no tags), so clips still concatenate."""
    chains = [f"[{i}:a]{_TRIM},apad=pad_dur={pause:.2f}[s{i}]" for i, pause in enumerate(list(pauses) + [0.35])]
    graph = ";".join(chains) + ";" + "".join(f"[s{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=0:a=1[out]"
    command = [ff, "-hide_banner", "-loglevel", "error", "-y"]
    for path in paths:
        command += ["-i", str(path)]
    command += ["-filter_complex", graph, "-map", "[out]", "-ac", "1", "-ar", "24000", "-c:a", "libmp3lame",
                "-b:a", "48k", "-write_xing", "0", "-id3v2_version", "0", "-map_metadata", "-1", "-f", "mp3", str(target)]
    subprocess.run(command, check=True, capture_output=True)


async def synthesize(clips, cache_dir, voices, concurrency=6):
    """Synthesize every clip into cache_dir/clips/<id>.mp3 (segments cached in cache_dir/segments). Each clip speaks
    with its own voices and rate (a grammar narrator, a little slower); `voices` covers clips made without them.
    A timed clip also gets clips/<id>.words.json, when each of its words is spoken (see clip_words)."""
    try:
        import edge_tts
    except ImportError as error:
        raise SpeechError("edge-tts is required: pip install edge-tts") from error
    ff = ffmpeg_exe() if any(len(c.parts) > 1 for c in clips.values()) else None
    cache_dir = Path(cache_dir)
    seg_dir, clip_dir = cache_dir / "segments", cache_dir / "clips"
    seg_dir.mkdir(parents=True, exist_ok=True)
    clip_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    joins = asyncio.Semaphore(4)
    downloads = {}                              # one download per segment, however many clips share it
    timed = {segment_id({**voices, **dict(c.voices)}[lang], spoken, c.rate)
             for c in clips.values() if c.timed for lang, spoken in c.parts}

    def segment(voice, spoken, rate):
        key = segment_id(voice, spoken, rate)
        if key not in downloads:
            downloads[key] = asyncio.ensure_future(fetch(voice, spoken, rate, seg_dir / f"{key}.mp3", key in timed))
        return downloads[key]

    async def fetch(voice, spoken, rate, path, marks):
        words = _words_file(path)
        if path.exists() and path.stat().st_size > 256 and (not marks or words.exists()):
            return path
        async with semaphore:
            last, limit = None, _time_limit(spoken)
            for attempt in range(TRIES):
                try:
                    temporary, told = path.with_suffix(f".part{attempt}"), words.with_suffix(f".part{attempt}")
                    request = _communicate(edge_tts, spoken, voice, rate or "+0%", marks).save(
                        str(temporary), str(told) if marks else None)
                    await asyncio.wait_for(request, limit)
                    require(temporary.stat().st_size > 256, "empty audio returned")
                    if marks:
                        told.replace(words)
                    temporary.replace(path)
                    return path
                except Exception as error:      # network and provider errors vary by release; the time limit too
                    last = error
                    temporary.unlink(missing_ok=True)
                    told.unlink(missing_ok=True)
                    if attempt + 1 < TRIES:
                        await asyncio.sleep(RETRY_SECONDS * (attempt + 1))
            # a timeout has no message of its own: name its type, so the reason is never empty
            raise SpeechError(f"TTS failed for {spoken[:60]!r} ({TRIES} tries of at most {limit:.0f} s): "
                              f"{str(last) or type(last).__name__}")

    async def clip(item):
        target, words = clip_dir / f"{item.clip_id}.mp3", clip_dir / f"{item.clip_id}.words.json"
        if target.exists() and target.stat().st_size > 256 and (not item.timed or words.exists()):
            return target
        own = {**voices, **dict(item.voices)}
        paths = [await segment(own[lang], spoken, item.rate) for lang, spoken in item.parts]
        temporary = target.with_suffix(".part")
        if len(paths) == 1:
            temporary.write_bytes(paths[0].read_bytes())
        else:
            async with joins:
                await asyncio.to_thread(_join, paths, item.pauses, temporary, ff)
        if item.timed:                          # written with the clip it describes
            found = await asyncio.to_thread(clip_words, item, paths, ff)
            words.write_text(json.dumps([[round(at, 2), word] for at, word in found], ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        return target

    results = await asyncio.gather(*(clip(c) for c in clips.values()))
    return dict(zip(clips, results))
