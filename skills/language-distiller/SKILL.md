---
name: language-distiller
description: Distill language-course material (course-book or workbook pages, a teacher's lecture slides, handouts, scans or notes) into a compact learner sheet (vocabulary, grammar, useful phrases and a catchy closing story that reuses the lesson), with original examples and nothing that names the source, then optionally turn the finished units into one offline phone study app (neural audio that repeats sentences on tap and keeps playing with the screen off, an examples-only listening mode, spaced-repetition flashcards, five lesson games) and MP3 listening episodes. German is the fully tested reference language; Spanish, Arabic (right to left) and Japanese (no spaces) have profiles; any other language gets a short language profile first. Use it whenever a language learner wants a lesson or course book turned into notes, study sheets, flashcards, audio, a listening story, study games or a phone app, even if they don't name the skill.
---

# Language Distiller

Turn a supplied lesson into a psychologically manageable substitute for rereading it, then make it easy to absorb on the phone. A lesson can be course-book and workbook pages, a lecture's slides, a teacher's handout or the learner's own notes.

**complete source inspection → intelligent learning compression → concise learner sheet → a story that brings it back to life**

Optimize for learning value per line, not extracted-item count. The analysis may be exhaustive; the HTML must not look like an audit, workbook, learning dashboard, or second textbook.

## The target language

Everything that depends on the language lives in one **language profile**, `languages/<code>.json`: the sheet's section names, the articles and their colours, the voice, what the speech splitter needs to find the language inside English, the small words the games ignore, and hints for the review (German: the Perfekt belongs on every verb card). The lesson's `target_language` picks the profile.

- **German (`de`)** is the reference: every rule below was built and tested with German, and its examples are German.
- **Spanish (`es`)** has a complete two-unit sample course (`examples/sample-course-es` in the skill's repository), reviewed by its author but not yet by a native speaker.
- **Arabic (`ar`)** and **Japanese (`ja`)** have profiles, each tested with a small original lesson built into a sheet and an app. Arabic is written right to left (`"direction": "rtl"`): every line on the sheet and in the app takes the direction of its first letter, so Arabic reads right to left beside its English. Japanese has no spaces between words (`"spaces": false`): word counts and the originality check count characters, Hör-Bingo finds words inside sentences, and Satzbau asks the phone's browser where the words are. Neither has been used with a real course or reviewed by a native speaker yet.
- **Any other language:** before the first lesson, write its profile following [languages.md](references/languages.md), then build one lesson end to end and review it with a speaker of the language before calling it supported. The scripts refuse a language without a profile.

The sheet uses the profile's section names (German `Wortschatz`, `Grammatik`, `Redemittel`, `Geschichte`; Spanish `Vocabulario`, `Gramática`, `Expresiones útiles`, `Historia`). The app keeps its German texts for a German course and speaks English to learners of every other language. This guide calls the sections vocabulary, grammar, Redemittel (useful phrases) and story.

## Non-negotiable learner output

Put new deliverables in the source's sibling folder `<filename without final extension> - Digested`. Preserve earlier versions and choose a new versioned filename.

The learner-facing HTML contains a small identifying header and exactly these sections, in this order:

1. vocabulary (German `Wortschatz`)
2. grammar (`Grammatik`)
3. Redemittel, the reusable phrases (`Redemittel`)
4. story (`Geschichte`): one original, catchy story that reuses the lesson

Do not render goals, Start routes, study instructions, article legends, navigation, source/review notes, coverage tables, cultural commentary sections, exercises, quizzes, summaries, "Later" material, progress UI, inventories, IDs or locations. Internal working JSON/reviews live under `_work` or `_skill_test`, never in the learner route. Read [section-spec.md](references/section-spec.md) before authoring.

**The learner output never names or copies its source.** No book title, publisher, ISBN, author, teacher or character names; no copied sentences, plots, places or statistics. Write the unit titles, every example and the story yourself. The source is identified only inside `_work`. List distinctive source names in the inventory's `private_terms` and in `course.json`, and the tools refuse output that contains them. Learners may want to share their notes; original wording is what makes the notes their own.

Work only from material the learner owns or is licensed to use, and keep sources local. Never publish anything on the learner's behalf.

Scripts live in this skill's `scripts/` folder. `<skill-dir>` below means the folder that contains this `SKILL.md`, wherever the client installed it. They need Python 3.10+ (`python` below; `py -3` on Windows, `python3` on some systems). Audio additionally needs `edge-tts`, `pyspellchecker` and ffmpeg (`imageio-ffmpeg` provides one).

## 1. Inspect the whole lesson internally

Read [source-extraction.md](references/source-extraction.md). Verify the actual lesson boundaries and inspect all relevant pages, picture vocabulary, margins, grammar/communication references, model texts and linked writing/speaking tasks. Text extraction is an aid, not visual inspection. Record missing audio internally and do not invent spoken-only content.

Create the internal inventory described in [data-contract.md](references/data-contract.md) before the lesson data. The inventory prevents silent omissions; it is not a list of things that must become cards.

For each candidate, ask:

> If the learner remembers this after finishing the lesson, will it materially improve their command of the language?

Classify it as:

- **standalone**: deserves focused learner attention;
- **embedded**: worth reinforcing inside a selected example, grammar pattern or expression, but not worth another card;
- **duplicate**: the same learning decision already has a home; or
- **excluded**: source detail with no meaningful learning payoff here.

Explicit grammar, an explicit word field or picture dictionary (German *Wortfeld/Bildlexikon*), and highly reusable communicative/writing patterns are essential and normally standalone. Names, dates, plot facts, one-off itineraries, routine instruction words and ordinary support vocabulary are usually excluded. Read [nugget-compression.md](references/nugget-compression.md) for the selection test. Do not use quotas as a substitute for judgment.

For a whole course, write one small Python author script per unit with [scripts/authoring.py](scripts/authoring.py) (`Pack(…, language="de")`): one call per card writes the lesson record and its inventory decision together, so they cannot drift; `seal()` chains the hashes before rendering. Editing a card later means editing one line and rerunning the script.

## 2. Write the three teaching sections

Author the structured lesson data from the selected inventory. The renderer must not mine old sheets, invent filler, or promote every source token. The data fields `de` and `en` hold the target-language text and its English gloss, whatever the language.

### Examples carry the teaching

Every example is heard, repeated and replayed in games hundreds of times, so each one must earn it. Read [example-sentence-rules.md](references/example-sentence-rules.md) and hold every sentence to three tests: an adult would really say it, it shows how the target works, and it is worth remembering. Specific beats generic; a B1 example usually carries one connector or second clause the course has taught. Reject silly, empty and A1-flat sentences (*Das Seminar ist interessant.*), sentences that depend on the book's plot, and anything copied from the source.

### Vocabulary

Choose vocabulary that the lesson explicitly teaches or meaningfully needs: complete small word fields and picture-dictionary sets, recurring topic words, words required for the lesson's speaking/writing goal, and useful level-appropriate collocations or constructions the lesson wants noticed.

Every chosen item earns its card and has one natural, translated example. A second example is only for a genuinely different important usage. Nouns show their article when the language has one (from the profile), their meaning and a useful plural. Verbs show the forms the learner must produce; for German that is the Perfekt (*hat/ist* + Partizip II, irregular forms marked "(!)"), reflexive form, separability, preposition/case or common construction when relevant, and the profile's `verb_hint` reminds the review.

Keep coherent small taught sets complete. Do not arbitrarily remove two items from seven workplace events merely to shorten the sheet. Conversely, appearing once in a reading does not make an ordinary word a vocabulary target.

### Grammar

Include every grammar point the lesson explicitly teaches, including a small but important rule such as German `außer + Dativ`. Separate concepts when that makes the choice easier to understand. For each point, teach compactly:

- meaning or purpose;
- the core rule;
- a usable pattern;
- normally 2–4 strong, translated examples; and
- one exception or contrast only when it prevents a likely misunderstanding.

Do not copy a whole reference chapter or omit a distinction because its box is small. Examples should carry much of the explanation. Grammar accuracy outranks aggressive compression.

### Redemittel (useful phrases)

Extract the best reusable templates from communication boxes, model texts, dialogues and productive tasks, especially writing. Cover the communicative jobs actually taught: invitations, replies, requests, reasons, opinions, formal email, small talk, complaints, or their lesson-specific equivalents.

Each card shows the reusable template first, a brief use cue, an English meaning and one natural example. Preserve placeholders (`…`) and concise formal/informal variants when they materially affect reuse. Do not copy full letters or create separate writing/reading/culture sections; all reusable language belongs here.

## 3. Write the story

Close every sheet with one short original story (four to seven paragraphs, 250–600 words) that puts the lesson back into a living context: a small plot with a pull, adult everyday life, some dialogue, concrete detail. It reuses at least 80 % of the vocabulary cards, every grammar point at least twice and at least half of the Redemittel, naturally, one or two lesson items per sentence. For a course, keep a recurring cast in `_work/story_bible.md` so each unit reads like the next episode. Each paragraph has a faithful English translation and lists the cards it uses with their exact forms; the sheet underlines them. Read [story-writing.md](references/story-writing.md).

## 4. Use examples for implicit reinforcement

Selected examples may naturally recycle a supporting source word, earlier grammar or another useful collocation. This is the preferred way to increase coverage without increasing card count. The sentence must still be short, natural and easy to repeat; it must have one clear primary target.

Do not hide an explicitly taught grammar rule or essential vocabulary item only inside someone else's example. Embedded coverage is for supporting material that genuinely improves the sentence, not for stuffing several unfamiliar decisions into one line. Record the exact embedded realization internally so it can be checked.

## 5. Review selection as well as accuracy

Run the mechanical validator, then use [quality-checklist.md](references/quality-checklist.md). Review in both directions:

- source → sheet: did an essential learning point disappear?
- sheet → source: does every card materially earn its space?

Check every target-language example, gloss, article/form, grammar statement, template, register and story sentence. Act on the validator's review notes (very short examples, the profile's verb hint, and anything "copied from the source"). For the originality check, the validator reads a PDF source's pages directly when `pymupdf` is installed; for slides, notes or a scan, save the lesson's text as UTF-8 and pass `--source-text`. Any six-word run shared with the source must be rewritten, in examples and in the story alike; only the card's own Redemittel frame may match. Independently compare the source when available, ideally through a separate reviewer such as a subagent that sees the pages and the lesson data; otherwise record an honest author second pass. Review findings and missing-media limitations remain internal or in the delivery message, never in the HTML.

Use the bundled version-2 pipeline:

```text
python <skill-dir>/scripts/study_pack.py validate --inventory L01_Inventory_v2.json --lesson L01_Lesson_v2.json --review L01_Review_v2.json --source "BOOK.pdf"
python <skill-dir>/scripts/study_pack.py render --inventory L01_Inventory_v2.json --lesson L01_Lesson_v2.json --review L01_Review_v2.json --source "BOOK.pdf" --output L01_Studysheet_v6.html
```

Without a completed review, render only to a filename containing `DRAFT`. Draft/review status is machine metadata, not learner-facing prose. Rendering creates only the HTML; internal evidence stays in `_work`.

Use [visual-design-system.md](references/visual-design-system.md) and the shared template. Run the HTML validator and, when possible, inspect desktop/mobile output. For a whole book, process and review each lesson separately and maintain an internal course map before claiming the full PDF is covered.

When the user requests audio for one sheet, read [embedded-audio.md](references/embedded-audio.md). It adds pronunciation controls that repeat a sentence until tapped again, and a header panel to listen to the whole lesson, only its examples or the story, each sentence 1–5 times, once or endlessly. Generate clear neural speech ahead of time and embed it; do not rely on browser speech synthesis or external media URLs. Audio generation through a hosted service requires explicit permission to transmit the selected learner text to that service.

When revising or regression-testing this skill, apply [evaluation-cases.md](references/evaluation-cases.md). They deliberately test both directions of failure: omitting real teaching value and exposing source noise.

Do not promise that a digest alone guarantees competence or exam success. It should deliver the lesson's concentrated learning value; listening, productive feedback and exam-specific performance require separate evidence. Read [competence-coverage.md](references/competence-coverage.md) only when making broader completion or exam-readiness claims.

Only read the flashcard references when the user explicitly requests Anki/CSV or a trainer. Those exports must use the same selected lesson data and must not broaden the learner sheet.

## 6. Turn finished units into a study app and listening episodes

When several units are reviewed and the learner wants to study on the phone, listen on the go, practise or play, read [course-app.md](references/course-app.md). It builds two deliverables from the same reviewed records, so nothing drifts:

- **one offline HTML study app** (German texts for a German course, English texts otherwise):
  - *Lernen* (Learn): all sheets with their stories. A 🔊 tap repeats until tapped again; a story sentence repeats on tap; an underlined story word shows its meaning. "🎧 Anhören" plays the whole lesson, only its examples, or the story, each sentence 1–5 times, once or endlessly, with the current sentence highlighted; a bar at the bottom pauses, goes back and skips, and *Weiter* goes on where a session stopped. A session plays as one audio track built on the phone, so it keeps going with the screen off, with ⏯ ⏮ ⏭ on the lock screen and the headphones.
  - *Üben* (Practise): one card per sheet card, spaced repetition, one tap per card.
  - *Spielen* (Play): five games per unit for days without motivation (Hör-Bingo, Wortpaare, Satzbau, an article game such as Der · Die · Das for a language with articles, Was sagt man?), made from the unit's own cards. Every round has exactly one right answer, and the build checks that (see [course-app.md](references/course-app.md)). Each game shows its progress and a 🔥 streak of right answers, and ends with *Fehler üben*, a round of only the questions the learner missed. After building an app, run `node <skill-dir>/scripts/inspect_games.mjs <chrome> <app.html>` (or paste `scripts/check_games.js` into the browser console with the app open): it plays every game at phone size like a hurried thumb and fails on a right answer shown as wrong, a round with two right answers, or a mistakes round that does not bring back what was missed.
- **MP3 episodes per unit** for commuting: the whole lesson with pauses to repeat and the story at the end; optionally an examples-only set where each sentence is repeated.

The target language is always spoken by its own voice (the profile's; German `de-DE-KatjaNeural`) and English by an English voice; target-language words inside English text are detected and switched (see [course-app.md](references/course-app.md)). For natural grammar audio, write `narration.json`: per grammar point a short spoken explanation in the target language at the learner's level (`de`), which the app and the episodes play, and an English backup (`en`) behind an EN button, with every target-language word marked «…» and placed after a colon or full stop. One narrator voice (the profile's, German `de-DE-SeraphinaMultilingualNeural`, a little slower) speaks both, so it sounds like one teacher (see [course-app.md](references/course-app.md)).

```text
python <skill-dir>/scripts/course_audio.py plan --course course.json                          # offline: what would be synthesized
python <skill-dir>/scripts/course_audio.py synth --course course.json --confirm-external-tts   # only after the user approved hosted TTS
python <skill-dir>/scripts/course_audio.py episodes --course course.json --confirm-external-tts
python <skill-dir>/scripts/course_audio.py episodes --course course.json --confirm-external-tts --kind examples --repeat 2
python <skill-dir>/scripts/build_course_app.py --course course.json --output Course_Studienpaket_v1.html
```

All units of a course share one target language. Only reviewed sheets go into the app. Without approval for hosted speech, build with `--no-audio`. The app is the course-level practice surface; it never changes the sheets. Name the course yourself (`"title": "Deutsch B1.1"`), never after the source.
