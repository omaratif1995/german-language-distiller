# Language profiles

Everything the skill does is the same for every language, except what is in the language's profile, `languages/<code>.json`. The lesson's `target_language` (`de`, `de-DE`, `es` …) picks it; a course needs one language for all its units. The scripts refuse a language without a profile and say which ones exist.

- **German (`de.json`)** is the reference. Every rule of this skill was built and tested with German.
- **Spanish (`es.json`)** has a complete two-unit sample course, `examples/sample-course-es` in the skill's repository (sheets and app, built with `make_sample.py`), reviewed by its author but not yet by a native speaker.
- **Arabic (`ar.json`)**, written right to left, and **Japanese (`ja.json`)**, written without spaces, each have a small original test lesson (`test_language.py`) that is built into a sheet and an app and played by `check_games.js`. Neither has been used with a real course or reviewed by a native speaker yet.

## What a profile holds

| Key | What it is | German |
|---|---|---|
| `code`, `name`, `native` | the language code, its English name (used in labels such as "Play German example" and "Build the Spanish sentence") and its own name | `de`, German, Deutsch |
| `voice` | the neural voice for the target language | `de-DE-KatjaNeural` |
| `narrator` | optional: `{"voice", "rate"}` of the voice that explains grammar in both languages, a multilingual one (`edge-tts --list-voices`, "Multilingual" in its name), so one person speaks the target language and English; `rate` a little slower | `de-DE-SeraphinaMultilingualNeural`, `-10%` |
| `sections` | the sheet's section names, also spoken as section titles: `vocabulary`, `grammar`, `redemittel`, `story` | Wortschatz, Grammatik, Redemittel, Geschichte |
| `translation` | the label that unfolds a story paragraph's translation | Übersetzung |
| `articles` | the articles a noun card can carry; `[]` for a language without articles (then nouns need none and the app has no article game) | der, die, das |
| `article_colours` | the colour each article borrows: `der` (blue), `die` (red) or `das` (green) | der → der … |
| `adjective_nouns` | German only: «ein Bekannter» in a noun's forms means the article game accepts der and die | true |
| `noun_plural` | optional, default true: noun forms must say the plural (set false for a language without plurals) | (true) |
| `first_person` | the word whose overuse at the start of examples the review flags | ich |
| `verb_hint` | optional: a pattern the forms of every verb card should match, and the review note when one does not | the Perfekt (`hat/ist`) |
| `direction` | optional, default `ltr`: `rtl` for a language written right to left (Arabic, Hebrew) | (ltr) |
| `spaces` | optional, default true: false for a language without spaces between words (Japanese, Chinese) | (true) |
| `sentence_start` | the letters a story sentence can begin with after . ! ? (as a regex class), also after a dialogue dash; a dash before a small letter (`—pregunta él`) goes on with the same sentence | `A-ZÄÖÜ`; Spanish adds `¿¡` and accented capitals; Arabic any Arabic letter |
| `abbreviations` | words before a full stop that ends no sentence | Dr, bzw, usw … |
| `ui` | the app's texts: `"de"` keeps the built-in German texts, `"en"` gives English (`UI_EN` in `scripts/language.py`), or a table of German text → your text | `"de"` |
| `bingo` | `function_words`: small words that never count as a lesson word in Hör-Bingo (in Japanese also the particles Satzbau may show alone); `verb_endings`: endings a verb's near forms are found by (erinnern → erinnert, 飲む → 飲みます); `inside_words`: true where small words join the next word (Arabic و، ب، ال), so a form also counts inside a longer word | sich, an, hat …; en, rn, ln |
| `speech` | how text is split and read (below) | |

`speech` holds:

- `spellchecker`: the `pyspellchecker` language (es, fr, it, pt, nl, ru, ar, lv, eu and more), or `null`. Without one, only the word lists and «…» marks decide which words are the target language.
- `letters`, `upper`, `lower`: the language's letters as regex classes (`A-Za-zÄÖÜäöüß`).
- `special`: letters English never has, which make a word the target language at once (`äöüß`, `ñ á é`).
- `words`: common words of the language, `ambiguous`: words it shares with English (German *die, an, so*), `articles`: articles and determiners that pull the next capitalised word into the language, `lone`: words that count as the language even alone (German *die*).
- `speakable`: how notation is read aloud (`→` "wird zu", `z. B.` "zum Beispiel"), in order.
- `german_notation`: German only: regional labels (A:, CH:), Konjunktiv II and optional letters (schütt(e)le).

## Adding a language

1. Copy `es.json` (or `de.json`) to `languages/<code>.json` and fill in every key: section names a teacher of the language would use, the articles and their colours, a voice from `edge-tts --list-voices`, the spellchecker code, the letters, common and shared words, the small words for Hör-Bingo, and how symbols are read aloud.
2. Decide the grammar focus for examples, the way German shows the Perfekt on every verb card, and add it to `verb_hint` and to the review.
3. Build one real lesson end to end, from inventory to sheet, app and a few audio clips (only with the learner's approval for hosted speech). Have a speaker of the language review the examples, the story and how the voice reads them.
4. Add a test like the ones `test_language.py` builds for Spanish, Arabic and Japanese, then call the language supported.

What stays the same for every language: the selection rules, the data contract, the story rules, the originality check, the listening engine, the games and the app.

## Right to left and without spaces

- **`"direction": "rtl"`** (Arabic, Hebrew): the sheet stays left to right for its English, and every line of text takes the direction of its first letter (`unicode-bidi: plaintext`), so an Arabic example reads right to left beside its English translation. The app does the same for its cards, game words and the listening line, and Satzbau lines its words up from the right.
- **`"spaces": false`** (Japanese, Chinese): word counts and the originality check count characters (two make a word, so twelve shared characters count as six copied words); Hör-Bingo finds a lesson word anywhere in a sentence, a verb also by its stem; a story sentence ends at 。！？. Satzbau asks the phone's browser for the words (`Intl.Segmenter`), keeps punctuation and the kana after a kanji with their word (食べ), and leaves out a sentence it breaks into a lone kana that is not a particle; a browser without `Intl.Segmenter` shows no Satzbau.
- Story sentences end at . ! ? … and ؟ before a letter of `sentence_start`, so write the sentence starts of your language there (Spanish ¿ ¡). A dialogue dash starts a sentence only before such a letter.

## Limits

- **Thai, Lao, Khmer, Burmese:** no spaces between words and no sentence punctuation (a space ends a sentence), so the story splitter needs a rule for them first.
- **Chinese:** works like Japanese, but has no profile yet; the lone-kana check does not apply, so check its Satzbau sentences in the app.
- **Scripts with joined letters or many marks** (Arabic, Devanagari): the words are counted with their vowel marks; test a lesson's Hör-Bingo and Satzbau on a phone before relying on them.
- **Word splitting in the browser** differs between browsers and versions; Satzbau only shows sentences that split into 5 to 9 sensible pieces.

## What the learner sees

- The sheet: the profile's section names, articles in the profile's colours, `<html lang>` from the code, and for a right-to-left language each line in its own direction.
- The app: a German course keeps the German texts (Lernen, Üben, Spielen, Anhören …). Any other course shows English texts, because a learner of a new language cannot always read its words yet; a profile with its own `ui` table can change that. Section names, the story label and the article game's title (*Der · Die · Das*, *El · La*) always come from the profile.
- The audio: the target language spoken by its own voice, English by an English voice.
