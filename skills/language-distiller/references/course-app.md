# Course study app and listening episodes

Use this when several units have reviewed sheets and the learner wants to study on the phone, listen on the go, practise with flashcards or play. Both deliverables are rendered from the same reviewed lesson records and sheets. They never change the sheets.

## course.json

Write one `course.json` (usually in `_work/`). Paths are relative to the file.

```json
{
  "title": "Deutsch B1.1",
  "subtitle": "Lektion 1–12 · Wortschatz · Grammatik · Redemittel · Geschichte",
  "narration": "narration.json",
  "voices": {"de": "de-DE-KatjaNeural", "en": "en-US-AvaNeural"},
  "cache": "audio",
  "episodes_dir": "../Audio",
  "new_per_day": 20,
  "private_terms": ["Menschen B1", "Hueber"],
  "units": [
    {"id": "L01", "label": "Lektion 1", "lesson": "L01/L01_Lesson_v2.json", "sheet": "../L01_Studysheet_v2.html"}
  ]
}
```

List units in course order. For two books in one course, give every unit a `group`, the book's short name (`"group": "B1.1"`), and keep each book's units together: the lesson picker then lists the books as headings, and Üben gets one chip per book. Use the newest reviewed sheet of each unit; drafts are refused. `new_per_day` sets the trainer's default for new cards per day (20 suits most learners; 25 suits a near exam date). `voices` and `narration` are optional; the voices shown are the defaults. Other keys are refused, so a misspelt key (`episodes_out` for `episodes_dir`) cannot silently fall back to a default folder.

**Name the course yourself, never after the source.** The title, subtitle, unit labels and lesson titles are spoken in the episodes and shown in the app. `private_terms` lists names that must never appear in the app or the episode names: the course book's distinctive title words, its publisher, the teacher. The tools refuse to write output that contains one.

## Pronunciation: the target language is always spoken by its own voice

German is the example below. Another language uses its profile's voice, word lists and dictionary in the same way ([languages.md](languages.md)); `course.json` may still set `voices`. All units of a course share one target language, and the app's own texts are German for a German course and English for any other.

Multilingual neural voices guess the language of each request, and the Edge service marks every request as American English. Short German words inside English ("als", "rund", "total") then come out with English pronunciation. `scripts/speech.py` therefore never asks a voice to switch language inside one request:

- German text (headwords, examples, frames, variants, story sentences) goes to the German voice in one piece.
- English text (glosses, use cues, explanations) is split into language runs, and German words inside it go to the German voice. Detection uses:
  - word lists, plus the German and English `pyspellchecker` dictionaries and their word frequencies;
  - capitalisation, and an article before a capitalised word (`die Babysitter`);
  - hyphenated compounds (`S-Bahn`);
  - the neighbouring words.

  It also reads course-book notation: `A:` and `CH:` (Austrian and Swiss variants), `etw.`, `jdn.`, `(e)`, `→` and `…sten`.
- Forms lines (`abschließen = to complete`) are German notes; the side right of `=` is read as an English gloss.
- Each run is synthesized on its own. The clip trims each run's built-in silence and pauses by punctuation (also a comma or colon right after a German word), so it sounds like one speaker.
- Grammar explanations have **one narrator**: the profile's multilingual voice (German: `de-DE-SeraphinaMultilingualNeural`, at `-15%`) reads the German and the English runs alike, so an explanation sounds like one teacher, not two people taking turns. `voices.narrator` in `course.json` can name another one.

Before synthesizing, read the `plan` output and spot-check `<cache>/plan.json`, where `texts` shows every clip as `[de] …` and `[en] …` runs. Fix a mis-split note in the lesson data, not in the audio.

## Spoken grammar explanations (narration.json)

Without narration, `🔊 Erklärung` reads the grammar card itself: title, meaning, rule, patterns and contrast. That is correct, but it sounds like a list. For natural audio, write `narration.json` next to `course.json`, keyed by unit id and grammar id, with two versions of each point, written in short blocks:

```json
{"L01": {"g01": {
  "title": "als – ein Ereignis oder eine Zeit in der Vergangenheit",
  "de": "Für einen einzigen Moment in der Vergangenheit, oder für eine ganze Zeit in deinem Leben, sagt man: «als». Hör zu:\n> Als ich ein Kind war, hatten wir einen Hund.\nNach «als» steht das Verb ganz am Ende: «als ich ein Kind war». …\n! Aber Vorsicht: «Als» gibt es nur in der Vergangenheit. …",
  "patterns": [{"label": "als-Satz zuerst", "form": "Als + Subjekt … Verb (Ende), Verb + Subjekt …"}],
  "en": "«Als»: one event, or one period, in the past. … Listen:\n> «Als ich ein Kind war, hatten wir einen Hund.»\n…"}}}
```

- **`de`, the explanation in the target language,** is what `🔊 Erklärung`, *Ganze Lektion* and the MP3 episodes play: one voice in one language, read in one piece, so it flows like a teacher talking. Write it at the learner's level: short sentences, *du*, the grammar words the course uses (*Nebensatz*, *Verb am Ende*, *Genitiv*), 60–110 words. Name a word you talk about as a word ("Das Wort deshalb …"), so it is not heard as part of the sentence.
- **`en`, an English backup,** waits behind a small **EN** button for days when the target-language version is too hard. Mark every target-language word, phrase or sentence with «…», and put it **after a colon or a full stop, never inside an English sentence**: "For the present, you say: «wenn.»", not "Use «wenn» for the present". The narrator then changes language at a natural pause. Put the full stop inside the marks («wenn.»).
- **`title` and `patterns`** (optional) put the rest of the app's card in the target language: they take the place of the lesson's English title and pattern lines there. Keep the lesson's forms and translate only the labels and grammar words (*Subjekt*, *Verb (Ende)*). The sheets keep the reviewed lesson as it is.
- A plain string instead of the two versions is an English-only explanation (older narration files).

**Written in blocks, read along.** On the app's grammar card, the `de` explanation takes the place of the short English meaning, rule and contrast, and the `en` one is folded away under «Auf Englisch». The sentence being spoken lights up, and the page follows it while the learner reads along. Write each text in lines:

- a plain line is a paragraph;
- `> ` is an example (consecutive lines share one box);
- `! ` is the trap, shown with ⚠.

Mark the words you talk about with «…»: a form or a short word shows in bold, a longer piece in italics. Keep each «…» on one line. The voice reads the lines as one text, without the marks (in `en`, the marks still switch the language). An English example line is all one «…».

For both versions:

- **Order:** what it is for, the rule, one or two examples, the usual trap.
- **No symbols:** leave out `+`, `→` and `/`. Show endings through short phrases (say «am größten», not "-sten"); a word like *-ung* is read as "ung".
- **No wrong German aloud:** describe the mistake instead of saying it, because learners copy what they hear.
- **Original examples:** quote the sheet's own examples or new ones, never the source's, and check the narration for six-word runs shared with the source like any example.
- **A little slower:** the narrator speaks at the profile's rate (German `-15%`, about 14 % longer than normal speech), which gives a grammar point time to land and leaves time to read along; at `-20%` it starts to drag.

Without a narrator voice in the profile, `de` is read by the target voice and the `en` runs alternate between the two voices. `plan` refuses narration for unknown unit or grammar ids, keys other than `de`, `en`, `title` and `patterns`, patterns that are not `{"label", "form"}`, and «…» that do not close in turn. It lists unmarked words in `en` that look German, and English example lines that are not all one «…».

The narration clips are **timed**: `synth` asks the voice service for the time of every word and keeps it beside the clip (`<cache>/clips/<id>.words.json`); in a clip joined from runs, each run's times move by the silence trimmed from it. The app matches the written sentences to the spoken words letter by letter, so a symbol read out, or a word said differently, does not shift a sentence. A clip made before timings existed is made again.

## Audio commands

`course_audio.py plan` works offline. It writes `<cache>/plan.json` with each unit's listening order, the German controls (headwords, examples, phrases, variants, story sentences), the grammar explanation chain and the episode announcements, and reports how many clips are not yet in `<cache>/clips`. Clip ids depend on the voices, the spoken runs and their pauses. Unchanged clips are never synthesized twice, and runs shared by several clips are fetched once.

`course_audio.py synth --confirm-external-tts` sends the missing texts to the Edge TTS service. Ask first and say what is sent: the example sentences, glosses, explanations and stories of the selected units, nothing else. Each request has a time limit (a minute, plus a second for every five characters) and four tries, so a connection lost while the computer sleeps ends `synth` with a message instead of leaving it waiting. Run it again: the clips already made are kept.

`course_audio.py episodes` builds one MP3 per unit in `episodes_dir`, in the sheet's listening order:

- vocabulary: headword, English meaning, forms, German example, English translation;
- grammar: the spoken explanation, then its examples;
- Redemittel: frame, use and examples;
- Geschichte: the story, read straight through with a breath after each paragraph.

After every German teaching item there is a pause about as long as the clip, so the learner can repeat it aloud (shadowing). Expect roughly 15–30 minutes per unit.

`course_audio.py episodes --kind examples --repeat 2` builds a second set in `episodes_dir/Beispiele`: only the unit's example sentences, each German sentence played twice with a pause to repeat it, then its English meaning. These are the commuting drill: short, dense and made for repetition with the screen off.

Requirements: `pip install edge-tts pyspellchecker imageio-ffmpeg` (or a system ffmpeg).

## App

`build_course_app.py --course course.json --output <Name>_Studienpaket_vN.html` (or `--no-audio`; `--no-english` leaves out the English meanings and translations, a quarter less audio).

The app has four tabs: **Lernen**, **Hören**, **Üben** and **Spielen** (without audio there is no Hören).

**Lernen**
- All reviewed sheets in course order, a unit picker with ‹ › (by book, when units have a `group`), and a search over all cards that shows each hit under its unit and subheading, without the empty ones.
- 🔊 on every German headword, example, phrase and variant. **A tap repeats**: by default the clip plays again and again, with a short pause, until the learner taps it again or presses ⏹. The listening panel switches this to 1× or 3×.
- `🔊 Erklärung` on each grammar point plays its spoken explanation once. With narration, the card shows it written out, and the sentence being spoken lights up (also during *Ganze Lektion*); **EN** plays the English one and opens it under «Auf Englisch».
- The **Geschichte** at the end of each unit: a **🔊 Ganze Geschichte** button on the story header to play the whole story straight through, a 🔊 per paragraph, and a tap on any sentence repeats that sentence. A tap on an underlined word shows its meaning and speaks it.
- **🎧 Anhören** opens a small panel in the unit's header:
  - **▶ Weiter** (once a session was stopped): goes on where it stopped;
  - five ways to listen: **Ganze Lektion** (German vocabulary and expressions, grammar explained, then the story), **Wörter** (the words and the Redemittel), **Nur Beispiele** (only the German example sentences), **Grammatik** (each explanation, then its examples) and **Geschichte**;
  - **Sprache Nur Deutsch · Deutsch + Englisch**: with English, every word or phrase is followed by its meaning and every example by its translation, once, after the German plays (explanations and stories stay German);
  - **Jeder Satz 1× · 2× · 3× · 5×**: how often each German sentence is played before the next one;
  - **Am Ende Einmal · ⟳ Endlos**: stop at the end, or start the unit again;
  - **🔊-Taste 1× · 3× · ∞**: what a single 🔊 tap does.

  The session is joined on the device into one continuous audio track with lock-screen and headphone controls (⏯ ⏮ ⏭), so playback continues when the phone screen turns off; when the screen is on, the current card or sentence is highlighted and scrolled into view. A bar at the bottom shows what is playing, with ⏮ (this sentence again; right at its start, the one before), ⏸ / ▶ (pause, then go on in the same sentence), ⏭ (the next sentence now) and ✕ (end). A 🔊 tap during a session pauses it and plays that clip; when the clip stops, the session waits, paused, in the bar. Settings changed during a session apply at once, and all settings are remembered.

  Pauses separate without dragging: before the same sentence again about 0.8 s after a word and 1.35 s after a sentence; before the next one about 1.5–2 s after an example, less after headwords and story sentences, more at the end of a paragraph. They are measured from the voice: each clip's own lead-in and tail are trimmed when the track is built.

**Hören**: the course to listen to, for the commute or a walk.
- **Was möchtest du hören?** Five tiles: **Alles** (each unit as in *Ganze Lektion*), **Wörter**, **Beispiele**, **Grammatik** and **Geschichten**. A tap starts; a tap on the one playing stops it.
- **Aus welchen Lektionen?** *Nur Lektion 16*, *Ab Lektion 16* (to the end of the course; the lesson is the one in the picker), one chip per book when units have a `group`, or *Alle Lektionen*.
- **So klingt es:** the same *Sprache*, *Jeder Satz* and *Am Ende* as the panel, shared with it; *⟳ Endlos* starts the whole choice again.
- Unit after unit, each opening with its spoken name. Each unit is one track, as in the panel, and the next one is built while the last plays, so it goes on at once, also with the screen off; the bar names the unit (*Lektion 14 · 3 / 57*). A card at the top shows what is heard, big: the sentence or word, and its English when the learner listens with English.
- **▶ Weiter** goes on where a stopped session stopped, across units. Lernen and Hören share a running session: in Lernen it shows the unit being heard, highlights the card and lights the spoken sentence; choosing another lesson does not stop it. Üben and Spielen stop it, since they make their own sounds.

**Üben**
- One card per sheet card. Vocabulary goes German → English, with English → German optional. Grammar shows its title and asks for the rule and examples. Redemittel show the situation and meaning in English and ask for the German frame, because that is the choice the learner makes while speaking or writing.
- A card takes one tap, and ✓ Gewusst and ✗ Nochmal are visible from the start:
  - **✓** (or swipe right, →, 2): known, and the next card appears. The answer of the card just passed stays below for a few seconds with "Rückgängig" (or Backspace), in case the learner was wrong.
  - **✗** (or swipe left, ←, 1): the answer opens, and "Weiter ›" (or a swipe, or Enter) moves on.
  - **Tapping the card** (or Space) only peeks at the answer.
- A double tap never grades the next card.
- Rounds of 10 cards with a short break screen. A daily summary offers "+10 neue Karten". The progress bar and streak survive reloads.
- Schedule: new cards from the chosen units, in course order up to the daily limit, interleaved with the due reviews of every unit, so choosing units (a new book, one lesson before a test) never pauses what the learner already practises. "Gewusst" moves a card through the intervals 1 → 3 → 7 → 14 → 30 → 60 days. "Nochmal" brings it back after three cards and restarts its interval.
- Settings live in a closed panel: units (one chip per book first, when units have a `group`), parts, direction, new cards per day, round size, browse mode, sound and the progress, counted over every unit, one line per book.
- **Sichern** saves the progress (cards, streak, game records) to a file. **Laden** adds a file's progress to the progress here: per card the state further on wins, per game the better result, and two streaks that touch become one (12 days up to yesterday in one app and today in the other: 13). So the backups of two book apps both go into one course app, nothing here is lost, and loading a file twice changes nothing. Cards the app does not have are left out.

**Spielen**: for days without motivation. Five short games per unit, made automatically from the unit's reviewed cards, so they never show anything the sheet does not teach and never show wrong German. Every round has exactly one right answer, and the build checks that:

- **🎱 Hör-Bingo.** A card of 4–9 lesson words. A sentence is played (without sound: shown with a gap); the learner taps a word of the card that it contains, or "Nicht auf meiner Karte". The build lists, for every example, the other words of the unit it contains: their lemma, the forms the lesson marks for them and near forms (*verpasse* for *verpassen*), without small words such as *sich* or *an*. The game calls only a sentence that holds no other word of the card, and a tap on any word of the card that the sentence really holds counts as right. A right answer moves on by itself; a wrong one shows the sentence, its meaning and the right word until the learner taps *Weiter*. A line is a BINGO. Trains listening for known words in new sentences.
- **🃏 Wortpaare.** Up to three rounds of three to five German words (with their article colours) and their meanings, all different within a round (seven pairs make rounds of 4 and 3, none is left out); tap a word, then its meaning. A German word speaks when tapped. Time and mistakes give the stars.
- **🧩 Satzbau.** The English meaning is shown; the learner taps the German words in the right order. Only plain sentences of 5–9 words are used: no colons, quotes, brackets or dashes, so there is one clear order and nothing but words to place. A wrong tile only shakes, and after two misses the right one glows. Trains word order, the heart of B1 grammar. In a right-to-left language the words line up from the right. In a language without spaces (Japanese) the phone's browser finds the words (`Intl.Segmenter`): punctuation and kana after a kanji stay with their word (食べ), and a sentence the splitter breaks into a lone kana that is not a particle is left out.
- **⚡ Der · Die · Das** (the article game: its buttons and title are the profile's articles, *El · La* for Spanish; a language without articles has no article game). Sixty seconds of the unit's nouns; streaks multiply the points, a miss comes back soon, and the end screen lists the articles to remember. A noun with two correct articles accepts both: an adjective noun whose forms show «ein Bekannter» (der/die Bekannte), or forms that name both (der or das Joghurt).
- **💬 Was sagt man?** A situation and three phrases from the lesson; the two wrong ones come from other groups and never repeat the right one's words. Pick the one that fits, then hear it and see it in use.

Every game shows how far the round is (a bar under its title; in the article game the bar is the clock) and a 🔥 streak of right answers in a row; a right answer gives a short pulse, and streaks of 3, 5 and 10 a little chord. The end screen gives one to three stars, the best streak and, after any mistake, **Fehler üben (n)**: a round of only what was missed (the missed words on the Bingo card, the missed sentences, nouns, situations or pairs; a missed noun comes twice, without the clock). A mistakes round says what it is and sets no record. The games menu counts the lesson's stars (★ 12 von 15 Sternen).

A tap is ignored for 0.3 s after a new question appears, so a tap meant for the last question never answers the next one. `scripts/check_games.js` checks a built app the way a learner's thumb would: it plays every game with double taps and taps right after a question changes, and reports a right answer shown as wrong, a Hör-Bingo sentence with two words of the card, a Satzbau sentence outside 5–9 words (or whose tiles do not make the sentence), two equal meanings in a Wortpaare round, an option shown twice, a progress bar that does not move and a streak that shows no 🔥. In Hör-Bingo and Was sagt man? it answers the first question wrong on purpose and checks that *Fehler üben* brings back exactly that. `python scripts/inspect_games.py <app.html> [--units L01,L02]` runs it on every unit in headless Chrome or Edge at phone size (375 × 812, touch) and exits with 1 on any problem, or with 2 and the reason when it cannot finish (no browser, or the app or its games did not finish in time); a browser console works too: paste the script with the app open. "🎲 Überrasch mich" starts a random one. Stars and records are kept per unit and go into the progress backup. Sound effects follow the Ton setting.

## Size and performance

German clips are embedded at 32 kbit/s, the explanations and the English meanings and translations at 24 kbit/s (`--english-bitrate`). A 16-unit course with spoken explanations is about 65 MB, or 85 MB with English; two books in one course about 130 MB, or 170 MB with English.

- **The first screen:** a small script in the page head hides every unit but the one the learner was on before the page reads them, and the bar shows the remembered tab and unit from the first paint. Without it the phone laid out the whole course while the page loaded, which took longer than reading it.
- **The sound:** the clips sit in per-unit text blocks after the app script, so the app works before the audio has finished loading; the English blocks come after all the German ones. A unit's sounds work as soon as the page has read its block, and are unpacked on first use. A 🔊 tap before then shows *wird vorbereitet …* and plays when they arrive; a card's word asked for in that time plays then too.

Measured with headless Chrome at 6× CPU slowdown, about a mid-range phone, on the 129 MB, 32-unit course: the app works after 1.9–2.4 s (4.4–4.7 s without the head script) and has loaded everything after 6–9 s; on a desktop it is about 1 s. With English (168 MB) the app works just as soon and the German sound arrives at the same time; the English, at the end of the file, adds about a fifth to the full load. For quick sharing or old phones, also build a `--no-audio` copy (2–3 MB) and hand over the MP3 episodes.

## Delivery notes

- **Sending it:** messengers and cloud drives handle the file; most mail servers reject 40 MB.
- **Android:** opens the file in Chrome with everything working.
- **iPhone:** the Files and messenger preview shows the text but runs no JavaScript, so audio, practice and games need a hosted link.
- **Screen off:** each listening session is joined into one continuous audio track with lock-screen and headphone controls (⏯ ⏮ ⏭), so playback continues with the screen off. The MP3 episodes also work in any music player.
- **Progress:** stays in one browser on one device. *Sichern* and *Laden* move it between devices, and from the apps of single books into one course app with both.

## Verify before delivery

1. Run the unit tests (`python -m unittest` in `scripts/`; the speech tests need `pyspellchecker`).
2. Open the app in a phone-sized browser at 360–430 px wide and check there is no horizontal scroll.
3. Check the practice flow:
   - ✓ moves on and offers undo, ✗ opens the answer, and a tap only peeks;
   - swipes grade in both directions;
   - the round break and the daily summary appear;
   - progress survives a reload, and *Laden* of a *Sichern* file adds to it (a second *Laden* of the same file changes nothing).
4. Check the listening: a 🔊 tap repeats until tapped again; the panel starts all three modes; the bottom bar stops them. Listen to one mixed clip: the German words in it must sound German. Test with the sound muted when other people are around.
5. Play one round of each game to its end screen, with one mistake, and play its *Fehler üben* round; or run `scripts/check_games.js`.
6. Fully decode one MP3 episode with ffmpeg, so that `-v error` prints nothing.
