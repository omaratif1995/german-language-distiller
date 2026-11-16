# Course study app and listening episodes

Use this when several units have reviewed sheets and the learner wants to study on the phone, listen on the go, practise with flashcards or play. Both deliverables are rendered from the same reviewed lesson records and sheets. They never change the sheets.

## course.json

Write one `course.json` (usually in `_work/`). Paths are relative to the file.

```json
{
  "title": "Deutsch B1.1",
  "subtitle": "Lektion 1–12 · Wortschatz · Grammatik · Redemittel · Geschichte",
  "narration": "narration.json",
  "more_examples": "more_examples.json",
  "dialogues": "dialogues.json",
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

**Name the course yourself, never after the source.** The title, subtitle, unit labels and lesson titles are spoken in the episodes and shown in the app. `private_terms` lists names that must never appear in the app or the episode names: the course book's distinctive title words, its publisher, the teacher. The tools refuse to write output that contains one. A term counts as a whole word in any case, in all the text the app shows, translations included: when a name is also an ordinary word (Rose and *rose*), reword the ordinary word.

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

## Extra grammar examples (more_examples.json)

A grammar card's own examples show the rule two or three times. For more practice, write `more_examples.json` next to `course.json` and name it there (`"more_examples": "more_examples.json"`). It is keyed by unit id and grammar id, and each item has exactly these four keys:

```json
{"L01": {"g01": [
  {"use": "daily", "de": "Kannst du mir helfen, den Tisch zu tragen?", "en": "Can you help me carry the table?", "targets": ["zu tragen"]},
  {"use": "writing", "de": "Ich bitte Sie, mir die Rechnung noch einmal zu schicken.", "en": "Please send me the invoice again.", "targets": ["zu schicken"]},
  {"use": "exam", "de": "Es ist nicht erlaubt, im Museum zu fotografieren.", "en": "Taking photos in the museum is not allowed.", "targets": ["zu fotografieren"]}
]}}
```

- **`use`** says where the sentence lives: `daily` (talk and messages), `writing` (e-mails, letters, posts, a CV) or `exam` (the kind of text an exam reads or asks for: notices, announcements, articles, formal letters). The app shows it as **Alltag**, **Schreiben** or **Prüfung**.
- **`targets`** are exact whole words or phrases of `de`, as for any example. Every occurrence is highlighted, so choose ones that occur once in the sentence.
- **Six per point** work well, two for each use: different situations, different words, and different forms (a question, the clause first or second, another person or tense). Write them yourself, check them for six-word runs shared with the source like any example, and never repeat a card's sentence.

`plan`, `synth` and the app build refuse unknown unit or grammar ids, other keys or uses, and targets that are absent or inside another word.

In the app the extras wait folded under the card's own examples, as **Mehr Beispiele (6)**, each with its tag, 🔊 and translation. They are read by the examples' voice, not the narrator. *Ganze Lektion*, *Beispiele* and *Grammatik* (in the 🎧 panel and in Hören) play them after the card's examples, with their English under *Deutsch + Englisch*, and open the fold when they get there. The MP3 episodes leave them out, so the episodes stay as long as they were.

## Dialogues (dialogues.json)

The story recycles a unit in a text to read and hear; a dialogue makes it something to **say**. Write `dialogues.json` next to `course.json` and name it there (`"dialogues": "dialogues.json"`): per unit one everyday conversation between two people, in which the unit's phrases, grammar and some of its words are used the way people use them.

```json
{"U3": {"title": "Ist hier noch frei?",
        "scene": {"de": "Ein volles Café am Samstag. Ben sucht einen Platz.", "en": "A busy café on a Saturday. Ben is looking for a seat."},
        "people": {"Anna": "de-DE-AmalaNeural", "Ben": "de-DE-ConradNeural"},
        "lines": [{"who": "Ben", "de": "Entschuldigung, ist hier noch frei?", "en": "Excuse me, is this seat free?",
                   "uses": [{"card": "e04", "form": "ist hier noch frei"}]}]}}
```

- **Lines that people really say.** Write the situation first (who, where, why), then a conversation of about 12–18 lines that someone at this level could have this week: meeting someone again, asking for advice, moving an appointment, a job interview, the doctor, the bank. Each line one or two short sentences, with the small words of speech (*ja, doch, mal, halt*). Use the unit's Redemittel where a speaker would; every grammar point at least once; words where they fit. A line that only shows off a word is a bad line.
- **Two people, two voices** of the course's language (`people`: name → voice; women and men, younger and older, so they never sound alike). The scene and the title are read by the course's own voice.
- **`uses`** name a card and the exact form in the line (a whole word or phrase, as in the story): words and phrases are underlined with their meaning, and `course_audio.py plan` reports what each dialogue uses, alone and with the story (`DIALOGUE: U3: 14 lines, 180 words; words 9/40 (with the story 36), grammar 3/3 (with the story 3), phrases 10/18 (with the story 15)`).
- `course_audio.check_dialogues` refuses fewer than 6 lines, one speaker, two speakers with one voice, a form that is absent or inside another word, overlapping underlines, an unknown card or unit, and any private term. Check the lines for originality as you check examples: no six words in a row from the source (`study_pack.copied_run`, with the line's own phrases protected).
- With a translation language, its file gives per unit `"dialogue": {"scene": "…", "lines": ["…", one per line]}`.
- The translations are written, not spoken: the dialogue is there to hear and say the target language, and its sound stays small (each line once, in its speaker's voice).

In the app the dialogue follows the story as the unit's last section, one bubble per line (the second person on the right), each with its speaker, 🔊 and translation. Its tools: **▶ Anhören** (the whole dialogue, as often as the 🔊 button repeats), **🗣 Nachsprechen** (after each line a pause as long as the line, to say it), **🎭 Du bist …** (one per speaker: the app speaks the other person; at each of the learner's lines it marks *🎤 Du bist dran*, waits as long as the line takes to say, then plays it, so they hear how it sounds) and **🙈 Text verstecken** (the lines to say stay blurred until heard; a tap shows one). A line under the tools says how to practise: listen, repeat line by line, then take a role, first with the text, then without.

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

## Translation languages

English is the lesson's own gloss language. Any other language with a profile in `languages/` (Arabic, `ar`, is the first) can be added as a translation language, one choice for the whole app: the app's own words stay German, only the translations change.

1. In `course.json`: `"translations": {"ar": "translations_ar.json"}`. The file holds, per unit, the translation of **every English text** of the unit: `{"L01": {"v01": {"gloss", "forms"?, "ex": [...]}, "g01": {"ex", "more"?, "explain"?}, "e01": {"gloss", "when", "register"?, "variants"?, "ex"}, "story": [...], "dialogue": {"scene"?, "lines": [...]}}}` (the dialogue only for a unit that has one). `course_audio.check_translations` refuses a gap: every unit and card is covered, counts equal the English ones, `explain` exists iff the card has an English-backup narration, `more` iff it has `more_examples`, `variants` iff the record has variants (their usage text only), and the story has one entry per paragraph.
2. **German inside a translation is marked «…»**, and nothing with Latin letters stands outside the marks (names of tenses, abbreviations such as «PDF», lesson references). The German voice speaks what is inside the marks, the translation's own voice the rest (a profile's `voice`; Arabic `ar-SA-ZariyahNeural`; the narrator speaks the explanations, a little slower).
3. Names of people and places are written the way the learner reads them in their own script, once, the same everywhere (keep a small glossary per course).
4. `course_audio.py synth --confirm-external-tts` sends the translations' texts to the hosted voice service, like any other text: only with the learner's approval.
5. In the built app every English text carries `data-tl="en"`, and its translation follows as an element of the same class with `data-tl`, `lang` and `dir`; `html[data-tl]` shows the chosen language only. A right-to-left language flips cards, games and listening line, keeps German «…» runs left-to-right (`<bdi dir="ltr">`) and drops italics. The first start asks which language (a card); afterwards a pill in Lernen and Spielen, and rows in Hören and Üben, change it. The games carry the same texts per language (`GT`), laid over the English ones. Steps of a listening session carry the translation clip next to the English one.
6. `inspect_games.py <app> --language ar` plays every game in that language.

## App

`build_course_app.py --course course.json --output <Name>_Studienpaket_vN.html` (or `--no-audio`; `--no-english` leaves out the English meanings and translations, a quarter less audio; `--audio-format opus` makes the sound about a third smaller for browsers that decode Opus: see *Size and performance*). The build stops before writing if a 🔊 button or a listening order would play a clip that the app does not embed.

The app has four tabs: **Lernen**, **Hören**, **Üben** and **Spielen** (without audio there is no Hören).

**Lernen**
- **A start card** at the top: the first time it explains the four tabs in four lines (*So lernst du am besten*, once, after the translation language is chosen; *Los geht’s* closes it). Afterwards it is *Heute*, with the 🔥 streak and one big next step: **Üben** (cards due and new ones, or *Für heute geschafft ✓*), **Weiterlernen** (the lesson left half way, at its card: *Lektion 3 · Karte 14 von 67*; or else the first lesson not yet read through that still has unseen cards), **Anhören** and **Spielen**. *Üben* and *Schwierige Karten* always start a round with ✓ and ✗, also when *Modus* was left on *Durchblättern*. The lesson picker shows how far each lesson is (*Lektion 1 · Erinnerungen · 38 %*: the share of its cards the learner knows, box 2 or higher). The card is hidden while searching.
- **A slim header**: only the four tabs stay on top while scrolling; the lesson picker, ‹ ›, language pill and search scroll away with the page (about 63 px stay, not 150).
- **▶ Lektion lernen** in each lesson's header (and *Weiterlernen* on the start card): a guided walk through the lesson's cards in order, each with its answer and sound already there (the headword is not repeated above it), *Weiter ›* / *‹* or a swipe, a progress bar (*12 / 67*). The app remembers the card (per device), so the walk goes on where it stopped. At the end the lesson counts as read and there is *Jetzt üben*, *Nächste Lektion*, *Nochmal ansehen*. Tapping the Üben tab leaves it for a plain round.
- **A round for one lesson** (*Jetzt üben* after the walk, *Diese Lektion üben* at the lesson's end): new cards come from this lesson only, due cards from every lesson as always; the bar says *🎯 Nur Lektion 3*. It lasts for this round: the lessons chosen under *Einstellungen* are not changed, and choosing lessons there ends it.
- **Schwierige Karten** on the start card (only when there are some): a round of the cards missed lately (box 0 or 1).
- **Lektion geschafft?** at the end of each lesson: *Diese Lektion üben* and *Nächste Lektion ›*.
- All reviewed sheets in course order, a unit picker with ‹ › (by book, when units have a `group`), and a search over all cards that shows each hit under its unit and subheading, without the empty ones.
- 🔊 on every German headword, example, phrase and variant. **A tap repeats**: by default the clip plays again and again, with a short pause, until the learner taps it again or presses ⏹. The listening panel switches this to 1× or 3×.
- `🔊 Erklärung` on each grammar point plays its spoken explanation once. With narration, the card shows it written out, and the sentence being spoken lights up (also during *Ganze Lektion*); **EN** plays the English one and opens it under «Auf Englisch».
- **Mehr Beispiele (6)** under a grammar card's own examples, with `more_examples.json`: folded, so the card stays short; open, each extra example shows its tag (*Alltag*, *Schreiben*, *Prüfung*), 🔊 and translation, and its targets are marked like any example's.
- The **Geschichte** at the end of each unit: a **🔊 Ganze Geschichte** button on the story header to play the whole story straight through, a 🔊 per paragraph, and a tap on any sentence repeats that sentence. A tap on an underlined word shows its meaning and speaks it; while something plays, it only shows the meaning, and the sound goes on.
- The **Dialog** after the story, with `dialogues.json` (see *Dialogues*): listen, say each line after the voice, take a role. The start card offers it every day (**🗨️ Sprechen üben**: the dialogue of the lesson being learnt).
- **🎧 Anhören** opens a small panel in the unit's header:
  - **▶ Weiter** (once a session was stopped): goes on where it stopped;
  - six ways to listen: **Ganze Lektion** (German vocabulary and expressions, grammar explained, then the story and the dialogue), **Wörter** (the words and the Redemittel), **Nur Beispiele** (only the German example sentences), **Grammatik** (each explanation, then its examples), **Geschichte** and **Dialog**;
  - **Übersetzung** (with more than one translation language: see *Translation languages*) a language segment, **👁 anzeigen** (the translation is shown beside every sentence, whether it is spoken or not) and **🔊 vorlesen** (every word or phrase is followed by its meaning and every example by its translation, once, after the German plays; explanations and stories stay German). Hear German only and still read the translation: 👁 on, 🔊 off;
  - **Tempo 0,6× · 0,7× · 0,8× · 0,9× · 1× · 1,2×**: how fast the voices speak, with the pitch kept; one tempo serves the whole app (every 🔊, the sessions, Hören, Üben) and is remembered. While a session plays, the bar's tempo button (*1×*) changes it at once, and the highlighted sentence stays in step;
  - **Wiederholen** a stepper − n + from 1 to 99 (no fixed list of choices: the learner sets whatever number they like): how often each German sentence is played before the next one;
  - **Nachsprechen aus · 🗣 mit Pause**: after each German sentence (its last play), a pause as long as the sentence and a breath, to say it aloud; listening becomes speaking practice;
  - **Am Ende Einmal · ⟳ Endlos**: stop at the end, or start the unit again;
  - **🔊-Taste 1× · 3× · ∞**: what a single 🔊 tap does.

  The session is joined on the device into one continuous audio track with lock-screen and headphone controls (⏯ ⏮ ⏭), so playback continues when the phone screen turns off; when the screen is on, the current card or sentence is highlighted and scrolled into view, but only while the learner follows it: once they scroll away, tap or scroll in the last few seconds, or have the 🎧 settings open, the highlight moves on without moving the page (until the sentence that plays is in view again; ⏮ ⏭ always go there). A title without a place on the page keeps the place being followed, and a setting changed during a session never moves the page. A bar at the bottom shows what is playing, with ⏮ (this sentence again; right at its start, the one before), ⏸ / ▶ (pause, then go on in the same sentence), ⏭ (the next sentence now) and ✕ (end). A 🔊 tap during a session pauses it and plays that clip; when the clip stops, the session waits, paused, in the bar. Settings changed during a session apply at once, and all settings are remembered.

  Pauses separate without dragging: before the same sentence again about 0.8 s after a word and 1.35 s after a sentence; before the next one about 1.5–2 s after an example, less after headwords and story sentences, more at the end of a paragraph. They are measured from the voice: each clip's own lead-in and tail are trimmed when the track is built.

**Hören**: the course to listen to, for the commute or a walk.
- **Was möchtest du hören?** Six tiles: **Alles** (each unit as in *Ganze Lektion*), **Wörter**, **Beispiele**, **Grammatik**, **Geschichten** and **Dialoge**. A tap starts; a tap on the one playing stops it.
- **Aus welchen Lektionen?** *Nur Lektion 16*, *Ab Lektion 16* (to the end of the course; the lesson is the one in the picker), one chip per book when units have a `group`, or *Alle Lektionen*.
- **So klingt es:** the same *Sprache*, *Wiederholen*, *Nachsprechen*, *Tempo* and *Am Ende* as the panel, shared with it; *⟳ Endlos* starts the whole choice again. With *Nachsprechen*, the commute becomes speaking practice: every German sentence, then a pause to say it.
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
- Settings live in a closed panel: units (one chip per book first, when units have a `group`), parts, direction, new cards per day, round size, browse mode, sound, *Tempo (Aussprache)* (the app's one tempo, with audio only) and the progress, counted over every unit, one line per book.
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

German clips are embedded at 32 kbit/s, the explanations and the English meanings and translations at 24 kbit/s (`--english-bitrate`), as MP3, which every browser plays. A 16-unit course with spoken explanations is about 65 MB, or 85 MB with English; two books in one course about 130 MB, or 170 MB with English.

**Opus (`--audio-format opus`)** embeds the same clips as Ogg Opus, 24 kbit/s for the target language and 20 kbit/s for the explanations and the English: the same two books with English are about 30% smaller (186 MB become 131 MB), and the page needs about a third less memory while it loads (on a desktop Chrome, 590 MB at its peak become 430 MB). Against the 48 kbit/s clips the voice service returns, the Opus clips are as close as the MP3s up to 4 kHz and closer from 4 to 8 kHz; the MP3s at these rates cut everything above about 8 kHz (the English ones above about 6), where Opus keeps the voice's top end. Opus takes about 1–2 dB off 1–6 kHz and 4 dB off 7–8 kHz at these rates (the same at 16 and at 48 kbit/s, gone at 64), so the build lifts those bands before encoding (`OPUS_EQ`); the decoded voice is then within 0.1 dB of the source's loudness and level to about 1 dB across the band. Clips keep their silences, so the player's pauses are the same. What it costs: the browser must decode Opus. Chrome (also on Android) and Firefox always do; Safari does from 18.4 (iOS 18.4), which is why MP3 stays the default. The app decodes a tiny Opus clip when it opens and shows a notice at the top if its browser cannot, instead of staying silent. Check a new build by ear (a few pairs, old against new, with the s, sch and z sounds), as the measures above are a guide, not a listening test.

- **The first screen:** a small script in the page head hides every unit but the one the learner was on before the page reads them, and the bar shows the remembered tab and unit from the first paint. Without it the phone laid out the whole course while the page loaded, which took longer than reading it.
- **The sound:** the clips sit in per-unit text blocks after the app script, so the app works before the audio has finished loading; the English blocks come after all the German ones. A unit's sounds work as soon as the page has read its block, and are unpacked on first use. A 🔊 tap before then shows *wird vorbereitet …* and plays when they arrive; a card's word asked for in that time plays then too.

Measured with headless Chrome at 6× CPU slowdown, about a mid-range phone, on the 129 MB, 32-unit course: the app works after 1.9–2.4 s (4.4–4.7 s without the head script) and has loaded everything after 6–9 s; on a desktop it is about 1 s. With English (168 MB) the app works just as soon and the German sound arrives at the same time; the English, at the end of the file, adds about a fifth to the full load. For quick sharing or old phones, also build a `--no-audio` copy (2–3 MB) and hand over the MP3 episodes.

## Delivery notes

- **Sending it:** messengers and cloud drives handle the file; most mail servers reject 40 MB.
- **Android:** opens the file in Chrome with everything working.
- **iPhone:** the Files and messenger preview shows the text but runs no JavaScript, so audio, practice and games need a hosted link.
- **Screen off:** each listening session is joined into one continuous audio track with lock-screen and headphone controls (⏯ ⏮ ⏭), so playback continues with the screen off. The MP3 episodes also work in any music player.
- **Progress:** stays in one browser on one device. *Sichern* and *Laden* move it between devices, and from the apps of single books into one course app with both.

## The web app (`--web`)

`build_course_app.py --course course.json --web site_v1 --audio-format opus` writes the app as a folder for an HTTPS host instead of one file (`scripts/web_app.py`):

- **`index.html`** is the same app without its sound. The sound is in `audio/au-<block>.<hash>.txt`, one file per block, in the same `id:base64;…` text the single file carries, named by its content: a rebuild keeps the names of unchanged blocks, so an update moves only the changed ones. The app fetches a block when one of its clips is first wanted.
- **`manifest.webmanifest`** and **`icons/`** (a speech bubble on the app's dark background, drawn by `web_app.py` without an image library): Chrome offers *Install app*, and the app opens from the home screen without the browser's bar.
- **`sw.js`**, a service worker. On the first visit it keeps every file for offline use: the bar under the tabs shows *Wird für offline gespeichert … %*, then *Offline bereit ✓*; if the download breaks (no network) the bar says *Das Speichern wurde unterbrochen* with *Erneut versuchen*, which resumes where it stopped, and *Nicht genug Speicherplatz auf dem Handy* when the phone has no room. Every later visit is answered from that copy, with or without a network. It looks for a new version when the app opens, when it comes back after half an hour, and every hour; a new version is fetched in the background (a file whose name did not change comes from the old copy), then the bar shows *Neue Version bereit* with *Aktualisieren*. Üben's settings have *Nach Updates suchen*. Progress stays: the same site keeps the same storage. Listening with the screen off and the lock-screen controls work as in Chrome, because the installed app is Chrome.
- **`login.html`**, **`404.html`**, **`_headers`**, **`robots.txt`** are for a private host. `404.html` matters on Cloudflare Pages: without it, Pages answers every unknown address with `index.html`, so an open path (the icons) would show the whole app. The service worker never answers `login.html`, so opening it reaches the host's login when a session has expired; the app offers *Anmelden* when an update check meets the login. `_headers` sets Cloudflare Pages' cache rules and `noindex`.

**Host it privately** when the course comes from a book: a public site publishes it (see the README's privacy notes). Cloudflare Pages behind Cloudflare Access (a login by an emailed code, free for a few users) works. Allow your own email for the site and its preview addresses, and let `manifest.webmanifest` and `icons/` through without the login (a Bypass rule), so Chrome can make the installed app from them. One file must stay under 25 MiB there; the build warns when one is bigger. `scripts/inspect_games.py` also plays the games of a web app at its address (`http://…`). A local server must send `.js` as JavaScript (Python's `http.server` on Windows sends `text/plain`, and the service worker then does not start).

## Verify before delivery

1. Run the unit tests (`python -m unittest` in `scripts/`; the speech tests need `pyspellchecker`).
2. Open the app in a phone-sized browser at 360–430 px wide and check there is no horizontal scroll.
3. Check the practice flow:
   - ✓ moves on and offers undo, ✗ opens the answer, and a tap only peeks;
   - swipes grade in both directions;
   - the round break and the daily summary appear;
   - progress survives a reload, and *Laden* of a *Sichern* file adds to it (a second *Laden* of the same file changes nothing).
4. Check the listening: a 🔊 tap repeats until tapped again; the panel starts all three modes; the bottom bar stops them; the bar's tempo button slows a running session at once and the highlighted sentence stays in step; *Grammatik* reaches the extra examples and opens their fold. Listen to one mixed clip: the German words in it must sound German. Test with the sound muted when other people are around.
5. Play one round of each game to its end screen, with one mistake, and play its *Fehler üben* round; or run `scripts/check_games.js`.
6. Fully decode one MP3 episode with ffmpeg, so that `-v error` prints nothing.
