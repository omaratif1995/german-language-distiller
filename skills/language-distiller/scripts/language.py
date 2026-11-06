#!/usr/bin/env python3
"""Language profiles: everything the skill needs to know about a target language.

A profile is `languages/<code>.json` (see references/languages.md): the section names of the sheet, the articles and
their colours, the voice, what the speech splitter needs to find the language inside English text, the small words
the games ignore, and hints for the review. German (`de.json`) is the reference profile.

The app's own texts are written in German. A German course keeps them as they are; every other course gets them in
English (UI_EN), or in the language of a `ui` table in its profile. `localize` swaps whole texts only: a whole
JavaScript string, a whole text between two tags, or a whole label, so «Satz» never changes inside «Satzbau».
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import re
import unicodedata

FOLDER = Path(__file__).resolve().parents[1] / "languages"
REQUIRED = {"code", "name", "native", "voice", "sections", "translation", "articles", "article_colours", "ui", "bingo",
            "speech"}
_cache = {}


class LanguageError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise LanguageError(message)


def code_of(tag):
    """The language code of a tag: de-DE → de."""
    return str(tag or "").split("-")[0].strip().lower()


def available():
    return sorted(path.stem for path in FOLDER.glob("*.json"))


def profile(tag="de"):
    """The profile of a target language; a missing profile is an error that says how to add one."""
    code = code_of(tag)
    if code not in _cache:
        path = FOLDER / f"{code}.json"
        require(path.is_file(), f"no language profile for {tag!r}: write languages/{code}.json (see "
                                f"references/languages.md); available: {', '.join(available())}")
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = sorted(REQUIRED - set(data))
        require(not missing, f"languages/{code}.json lacks {', '.join(missing)}")
        require(data["code"] == code, f"languages/{code}.json names code {data['code']!r}")
        require(set(data["sections"]) == {"vocabulary", "grammar", "redemittel", "story"},
                f"languages/{code}.json: sections needs vocabulary, grammar, redemittel and story")
        require(set(data["article_colours"]) == set(data["articles"])
                and set(data["article_colours"].values()) <= {"der", "die", "das"},
                f"languages/{code}.json: every article needs a colour, one of der, die or das")
        require(data.get("direction", "ltr") in ("ltr", "rtl"), f"languages/{code}.json: direction is ltr or rtl")
        require(data.get("spaces", True) in (True, False), f"languages/{code}.json: spaces is true or false")
        _cache[code] = data
    return _cache[code]


# ---------------------------------------------------------------- words and sentences ---
WORD_CHARS = 2          # without spaces between words (Japanese, Chinese), about two characters make a word
_rules = {}


def spaced(prof):
    """Whether the language puts spaces between its words (Japanese, Chinese and Thai do not)."""
    return prof.get("spaces", True)


def _in_word(char):
    return char.isalnum() or unicodedata.category(char)[0] == "M"      # letters, digits and the marks on them (ً, ि)


def word_spans(prof, text):
    """The words of a text, casefolded, with where each one stands: runs of letters and digits, or in a language
    without spaces every single character (WORD_CHARS of them count as one word)."""
    text = text.casefold()
    if not spaced(prof):
        return [(char, at, at + 1) for at, char in enumerate(text) if char.isalnum()]
    spans, start = [], None
    for at, char in enumerate(text + " "):
        if _in_word(char):
            start = at if start is None else start
        elif start is not None:
            spans.append((text[start:at], start, at))
            start = None
    return spans


def words(prof, text):
    return [word for word, _, _ in word_spans(prof, text)]


def word_count(prof, text):
    """How many words a text has: what stands between spaces, or its letters / WORD_CHARS without spaces."""
    return len(text.split()) if spaced(prof) else round(len(word_spans(prof, text)) / WORD_CHARS)


def run_length(prof, n):
    """n words, counted the way word_spans counts them."""
    return n if spaced(prof) else n * WORD_CHARS


def sentence_rules(prof):
    """(end, not_end) for story sentences: a sentence ends at . ! ? … ؟ before the next sentence's first letter
    (`sentence_start` of the profile: capitals in German, also ¿ ¡ in Spanish, any letter in Arabic), or at 。！？
    in a language without spaces; a full stop after an abbreviation of the profile, a single letter or a day's number
    (am 3. Mai) ends none. A dialogue dash starts a sentence only before such a letter: «—¿Algo más? —pregunta él»
    stays one sentence."""
    code = prof["code"]
    if code not in _rules:
        letters, start = prof["speech"]["letters"], prof.get("sentence_start", prof["speech"]["upper"])
        others = "".join("|" + re.escape(word) for word in prof.get("abbreviations", []))
        end = r"[.!?…؟]+[“”\"»«’)]*(?=\s+(?:[„“\"«»(" + start + r"0-9–-]|—[" + start + r"]))"
        if not spaced(prof):
            end = r"[。！？]+[」』）)]*|" + end
        not_end = rf"(?:(?<![{letters}])[{letters}]|(?<!\d)\d{{1,2}}{others})\.\Z"
        _rules[code] = (re.compile(end), re.compile(not_end))
    return _rules[code]


def narrator(prof):
    """The voice that explains grammar, in the target language and in English alike, and how fast:
    {"narrator": voice, "narrator_rate": "-15%"}; {} when the profile names none (then each language keeps its voice)."""
    found = prof.get("narrator") or {}
    return {"narrator": found["voice"], "narrator_rate": found.get("rate", "")} if found.get("voice") else {}


def article_class(prof, article):
    """The colour class of an article: German keeps der/die/das; another language borrows one of the three."""
    return prof["article_colours"].get(article, article)


def article_title(prof):
    """The title of the article game: «Der · Die · Das», «El · La»."""
    return " · ".join(article[:1].upper() + article[1:] for article in prof["articles"])


# German app text → English. Placeholders: {name} the language («Spanish»), {vocabulary} its vocabulary section.
UI_EN = {
    # Lernen and the app frame
    "Lernen": "Learn", "Üben": "Practise", "Spielen": "Play", "Vorherige Lektion": "Previous lesson",
    "Lektion wählen": "Choose a lesson", "Nächste Lektion": "Next lesson", "Suchen…": "Search…", "Suchen": "Search",
    "Audio, Üben und Spielen brauchen einen Browser mit JavaScript.": "Audio, practice and games need a browser with JavaScript.",
    "Karte": "card", "Karten": "cards", "gefunden": "found", "Lektionen": "Lessons",
    "🎧 Anhören": "🎧 Listen", "🔊 Erklärung": "🔊 Explanation", "Auf Englisch": "In English",
    "Ganze Geschichte anhören": "Listen to the whole story", "🔊 Ganze Geschichte": "🔊 Whole story",
    "Absatz anhören": "Listen to the paragraph",
    # Üben
    "Heute": "Today", "Keine Karten": "No cards",
    "Wähle in den Einstellungen Lektionen und Teile.": "Choose lessons and parts in the settings.",
    "Fertig für heute!": "Done for today!", "Karten geübt ·": "cards practised ·", "Heute ist nichts fällig.": "Nothing is due today.",
    "Tage in Folge": "days in a row", "Bis morgen!": "See you tomorrow!", "+10 neue Karten": "+10 new cards",
    "Durchblättern": "Browse", "Runde geschafft!": "Round done!", "gewusst": "known", "gewusst · ✗": "known · ✗",
    "nochmal": "again", "Noch": "Still", "Karten für heute": "cards for today", "Weiter": "Continue", "Pause": "Pause",
    "Gute Pause!": "Enjoy your break!", "Dein Fortschritt ist gespeichert.": "Your progress is saved.",
    "Weiter lernen": "Keep learning", "Tippen = Antwort ansehen": "Tap = see the answer", "Zurück": "Back",
    "Verstecken": "Hide", "Antwort zeigen": "Show answer", "Weiter ›": "Next ›", "✗ Nochmal": "✗ Again",
    "✓ Gewusst": "✓ Known", "Rückgängig": "Undo", "Deutsch → Englisch": "{name} → English",
    "Englisch → Deutsch": "English → {name}", "ohne Pause": "no break", "Tagesplan": "Daily plan", "Ton an": "Sound on",
    "Ton aus": "Sound off", "Neu": "New", "· Lerne ich": "· Learning", "· Sicher": "· Sure", "· Fest": "· Mastered",
    "1 Karte aus der Sicherung übernommen.": "1 card taken from the backup.",
    "{n} Karten aus der Sicherung übernommen.": "{n} cards taken from the backup.",
    "Dein Fortschritt hier bleibt erhalten.": "Your progress here is kept.",
    "In dieser Sicherung ist kein Fortschritt für diese Lektionen.": "This backup has no progress for these lessons.",
    "Neue Karten kommen aus den gewählten Lektionen. Fällige Karten kommen aus allen, damit du nichts vergisst.":
        "New cards come from the lessons you choose. Due cards come from all of them, so you forget nothing.",
    "Diese Datei ist keine Sicherung.": "This file is not a backup.",
    "Einstellungen": "Settings", "alle / keine": "all / none", "Teile": "Parts",
    "Richtung (Wortschatz)": "Direction ({vocabulary})", "Neue Karten pro Tag": "New cards per day",
    "Pause nach … Karten": "Break after … cards", "Modus": "Mode", "Ton (Aussprache und Spiele)": "Sound (pronunciation and games)",
    "Fortschritt": "Progress", "Sichern": "Back up", "Laden": "Load",
    "Der Fortschritt bleibt in diesem Browser auf diesem Gerät. Mit „Sichern“ nimmst du ihn mit.":
        "Your progress stays in this browser on this device. “Back up” lets you take it with you.",
    # Spielen
    "Neuer Rekord!": "New record!", "Nochmal": "Play again", "Andere Spiele": "Other games",
    "Hör-Bingo": "Listening Bingo", "🎱 Hör-Bingo": "🎱 Listening Bingo",
    "Hör einen Satz und finde das Wort auf deiner Karte.": "Hear a sentence and find its word on your card.",
    "Wortpaare": "Word Pairs", "🃏 Wortpaare": "🃏 Word Pairs",
    "Finde zu jedem Wort seine Bedeutung, so schnell du kannst.": "Match every word with its meaning, as fast as you can.",
    "Satzbau": "Sentence Builder", "🧩 Satzbau": "🧩 Sentence Builder",
    "Tippe die Wörter in die richtige Reihenfolge.": "Tap the words in the right order.",
    "60 Sekunden: Welcher Artikel passt?": "60 seconds: which article fits?",
    "Was sagt man?": "What do you say?", "💬 Was sagt man?": "💬 What do you say?",
    "Welche Wendung passt zur Situation?": "Which phrase fits the situation?",
    "als Spiel: ein paar Minuten, ganz ohne Lernstress.": "as a game: a few minutes, no study stress.",
    "· Rekord": "· Record", "🎲 Überrasch mich": "🎲 Surprise me",
    "Diese Lektion hat zu wenige Karten für ein Spiel.": "This lesson has too few cards for a game.",
    "Hör den Satz. Kommt ein Wort deiner Karte darin vor? Tippe es an.":
        "Listen to the sentence. Is a word from your card in it? Tap it.",
    "Lies den Satz. Welches Wort fehlt? Ist es auf deiner Karte?": "Read the sentence. Which word is missing? Is it on your card?",
    "🔊 Nochmal": "🔊 Again", "Nicht auf meiner Karte": "Not on my card", "👂 Hör gut zu …": "👂 Listen carefully …",
    "✓ Richtig,": "✓ Right,", "ist nicht auf deiner Karte.": "is not on your card.", "Auf deiner Karte:": "On your card:",
    "Nicht auf deiner Karte:": "Not on your card:", "Fehler:": "Mistakes:",
    "Du hast {n} Sätze gehört und {w} Wörter gefunden.": "You heard {n} sentences and found {w} words.",
    "Du hast {n} Sätze gelesen und {w} Wörter gefunden.": "You read {n} sentences and found {w} words.",
    "Bau den deutschen Satz: Tippe die Wörter der Reihe nach an.": "Build the {name} sentence: tap the words in order.",
    "Fehlerfrei:": "Without mistakes:", "von": "of", "Sätzen": "sentences", "🔊 Anhören": "🔊 Listen",
    "Geschafft, mit 1 Fehler.": "Done, with 1 mistake.", "Geschafft, mit {n} Fehlern.": "Done, with {n} mistakes.",
    "✓ Perfekt!": "✓ Perfect!", "Punkte": "points", "Punkte · beste Serie": "points · best streak", "Merk dir:": "Remember:",
    "Kein einziger Fehler!": "Not a single mistake!",
    "Lies die Situation und wähle die passende Wendung.": "Read the situation and choose the phrase that fits.",
    "Richtig:": "Right:", "✓ Genau!": "✓ Exactly!", "So sagt man es:": "That's how you say it:",
    "Tippe ein deutsches Wort und dann seine Bedeutung.": "Tap a {name} word, then its meaning.", "Runde": "Round",
    "Zeit:": "Time:", "s · Fehler:": "s · Mistakes:",
    "★ {n} von {m} Sternen": "★ {n} of {m} stars", "Fehler üben ({n})": "Practise mistakes ({n})",
    "Nur deine Fehler aus der letzten Runde.": "Only your mistakes from the last round.", "🔥 Beste Serie:": "🔥 Best streak:",
    # listening
    "Ganze Lektion": "Whole lesson", "Nur Beispiele": "Examples only", "▶ Ganze Lektion": "▶ Whole lesson",
    "▶ Nur Beispiele": "▶ Examples only", "wird vorbereitet …": "preparing …", "⟳ Runde": "⟳ Round",
    "Wiedergabe": "Playback", "⏹ Stopp": "⏹ Stop", "Beenden": "End", "Stopp": "Stop", "Einmal": "Once",
    "⟳ Endlos": "⟳ Endless", "∞ bis Stopp": "∞ until stop", "▶ Weiter:": "▶ Continue:", "Wort": "Word",
    "Erklärung": "Explanation", "Absatz": "Paragraph", "Satz": "Sentence", "Wiederholen": "Repeat", "je": "each",
    "Jeder Satz": "Each sentence", "Am Ende": "At the end", "🔊-Taste": "🔊 button", "Noch einmal": "Again",
    "Noch einmal (am Satzanfang: zurück)": "Again (at the start of a sentence: back)", "Nächster Satz": "Next sentence",
    "Beispiele": "Examples",
}


def ui_table(prof):
    """German app text → the text this course shows: nothing to change for German, English (or the profile's own
    table) for any other language, with the profile's section names and article game title."""
    if prof["ui"] == "de":
        return {}
    table = dict(UI_EN)
    if isinstance(prof["ui"], dict):
        table.update(prof["ui"])
    sections = prof["sections"]
    names = {"{name}": prof["name"], "{vocabulary}": sections["vocabulary"]}
    for key, value in list(table.items()):
        for placeholder, name in names.items():
            value = value.replace(placeholder, name)
        table[key] = value
    title = article_title(prof)
    table.update({"Wortschatz": sections["vocabulary"], "Grammatik": sections["grammar"], "Redemittel": sections["redemittel"],
                  "Geschichte": sections["story"], "▶ Geschichte": "▶ " + sections["story"],
                  "Der · Die · Das": title, "⚡ Der · Die · Das": "⚡ " + title})
    return {key: value for key, value in table.items() if key != value}


def localize(text, table):
    """Swap whole German texts for their translation: whole '…' JS strings, text between tags, and labels."""
    if not table:
        return text
    alternatives = "|".join(re.escape(key) for key in sorted(table, key=len, reverse=True))

    def js(match):
        return match[1] + match[2] + table[match[3]].replace("\\", "\\\\").replace("'", "\\'") + match[4] + match[5]

    def markup(match):
        return match[1] + match[2] + html.escape(table[match[3]], quote=True) + match[4] + match[5]

    text = re.sub(r"(')(\s*)(" + alternatives + r")(\s*)(')", js, text)
    text = re.sub(r"(>)(\s*)(" + alternatives + r")(\s*)(<)", markup, text)
    return re.sub(r'((?:aria-label|title|placeholder)=)(")(' + alternatives + r')()(")', markup, text)
