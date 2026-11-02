# Structured authoring contract — version 2

Version 2 separates exhaustive internal inspection from selective learner content. Use three UTF-8 JSON files under `_work` or `_skill_test`:

- `LNN_Inventory_v2.json`: source regions and candidate decisions;
- `LNN_Lesson_v2.json`: only content for the three learner sections;
- `LNN_Review_v2.json`: source, selection and language review.

The learner HTML exposes none of these records.

## Inventory

```json
{
  "schema_version": 2,
  "lesson_id": "L12",
  "book": "MENSCHEN B1 KURSBUCH",
  "source_sha256": "64 lowercase hexadecimal characters",
  "scope_label": "Lesson 12 print pages and linked reference; audio not supplied",
  "scope_pages": [74, 75, 76, 77, 78, 79],
  "pages": [
    {"pdf_index": 74, "folio": "73", "regions": [
      {"id": "p74-picture", "label": "workplace-event picture vocabulary", "status": "reviewed", "method": "visual+text", "note": "Seven labels visually checked."}
    ]}
  ],
  "items": [
    {
      "id": "i-v01",
      "kind": "vocabulary",
      "label": "der Betriebsausflug",
      "importance": "essential",
      "sources": [{"pdf_index": 74, "region": "p74-picture", "evidence": "explicit event label"}],
      "decision": "standalone",
      "home": "v01",
      "reason": "Part of the lesson's explicit seven-item workplace-event field."
    },
    {
      "id": "i-s01",
      "kind": "vocabulary",
      "label": "stattfinden",
      "importance": "supporting",
      "sources": [{"pdf_index": 75, "region": "p75-model", "evidence": "event takes place in May"}],
      "decision": "embedded",
      "home": "v01",
      "realization": "findet dieses Jahr im Mai statt",
      "reason": "Useful event collocation reinforced naturally without another card."
    }
  ],
  "dependencies": [
    {"id": "audio-1-41", "kind": "audio", "locator": "track 1.41", "status": "missing", "impact": "Spoken-only content and listening performance are not reviewed."}
  ],
  "private_terms": ["Menschen B1", "Hueber", "Herr Kaminski"]
}
```

`book` and `scope_label` identify the source internally; the learner never sees them. `private_terms` (optional) lists names that must never reach learner output: the source's distinctive title words, publisher, author or teacher, and its character names. The validator refuses any learner string that contains one as a whole word, and any ISBN. Choose terms that cannot occur in ordinary German (not *Menschen* on its own).

Each meaningful source region has at least one candidate or source-only record. `status` is `reviewed`, `pending` or `unreadable`; `method` is `visual`, `text` or `visual+text`.

Candidate `kind` is `vocabulary`, `grammar`, `expression` or `source_only`. Candidate `importance` is:

- `essential`: explicit/central teaching value; must resolve to a standalone home;
- `supporting`: worthwhile but may be standalone or embedded;
- `incidental`: detail/instruction/noise; excluded from learner content.

Decisions:

- `standalone`: requires `home` and source-specific `reason`;
- `embedded`: supporting only; requires `home`, an exact visible `realization`, and `reason`;
- `duplicate`: requires `duplicate_of` and `reason`, and must resolve to a standalone candidate of the same kind;
- `exclude`: incidental only; requires source-specific `reason`;
- `pending`: unresolved and blocks reviewed release.

The exact embedded realization must occur in its target card’s learner-visible strings. Embedding can reinforce supporting vocabulary or a familiar construction; it cannot replace an essential grammar point, explicit word-field item or major reusable phrase.

Dependencies stay internal. `missing` may limit the claimed scope without blocking a reviewed print-only sheet. `pending` or supplied-but-unreviewed media blocks release.

## Lesson

Only these top-level keys are accepted (`story` is optional for older lessons and standard for new ones):

```json
{
  "schema_version": 2,
  "lesson_id": "L12",
  "inventory_sha256": "hash of final inventory bytes",
  "title": "Ausflug des Jahres",
  "level": "B1",
  "target_language": "de",
  "gloss_language": "en",
  "vocabulary": [],
  "grammar": [],
  "redemittel": [],
  "story": {"title": "…", "paragraphs": []}
}
```

`title` is the learner's title for the unit, written from its topic, not the source's chapter title.

`target_language` is a language code with a profile in `languages/` (`de`, `de-DE`, `es` …; see [languages.md](languages.md)); every unit of a course has the same one. The text fields `de` and `en` in examples and story paragraphs hold the target-language text and its English gloss, whatever the language: the names stayed from the German original.

### Vocabulary record

```json
{
  "id": "v01",
  "group": "Betriebliche Veranstaltungen",
  "lemma": "Betriebsausflug",
  "pos": "noun",
  "article": "der",
  "forms": "Plural: die Betriebsausflüge",
  "gloss": "company outing",
  "examples": [{
    "de": "Unser Betriebsausflug findet dieses Jahr im Mai statt.",
    "en": "Our company outing takes place in May this year.",
    "targets": ["Betriebsausflug"]
  }]
}
```

Every selected item has one example. Two are allowed when they teach different important uses. German nouns require `der/die/das` and a useful plural or explicit no-plural note. `forms` may be empty for another part of speech when no form/complement information earns a visible line. German verb lemmas must retain the actual verb and any reflexive marker; put complements in `forms`.

### Grammar record

```json
{
  "id": "g01",
  "title": "Genitiv: belonging or association",
  "meaning": "The genitive often shows who something belongs to or is associated with.",
  "rule": "Masculine/neuter use des/eines and the noun usually adds -(e)s; feminine/plural use der/einer.",
  "patterns": [
    {"label": "masculine/neuter", "form": "des/eines + noun -(e)s"},
    {"label": "feminine/plural", "form": "der/einer + noun"}
  ],
  "contrast": "Explain adjective endings separately if the lesson teaches them.",
  "examples": [
    {"de": "Das ist der Bericht des Betriebsrats.", "en": "That is the works council's report.", "targets": ["des Betriebsrats"]},
    {"de": "Das ist das Ende eines Jahres.", "en": "That is the end of a year.", "targets": ["eines Jahres"]}
  ]
}
```

`contrast` is optional and omitted when it adds no important clarification. Use enough examples to teach the actual distinction—normally 2–4, not an inflexible maximum.

### Redemittel record

```json
{
  "id": "e01",
  "group": "Einladen und antworten",
  "frame": "Ich wollte mich erkundigen, ob …",
  "gloss": "I wanted to ask whether …",
  "when": "Politely request information in an email or formal conversation.",
  "register": "polite; formal/neutral",
  "variants": [],
  "examples": [{
    "de": "Ich wollte mich erkundigen, ob wir etwas mitbringen sollen.",
    "en": "I wanted to ask whether we should bring anything.",
    "targets": ["Ich wollte mich erkundigen, ob"]
  }]
}
```

`register` and `variants` are optional. A variant is `{form, usage}` and is used only when combining it saves repetition without obscuring a meaningful difference.

### Story record

```json
"story": {
  "title": "Sonne für alle",
  "paragraphs": [
    {"de": "Unser Betriebsausflug findet dieses Jahr am Bodensee statt. Alle freuen sich seit Wochen darauf.",
     "en": "Our company outing takes place at Lake Constance this year. Everyone has been looking forward to it for weeks.",
     "uses": [{"card": "v01", "form": "Betriebsausflug"}]}
  ]
}
```

At least three paragraphs. Each `uses` entry names a lesson card and the exact `form` that realizes it in the paragraph; the form must stay inside one sentence. Vocabulary and Redemittel forms are underlined (their first occurrence per paragraph) and must not overlap; grammar forms are only counted. Coverage is checked: a story that never uses a grammar point, or uses fewer than 60 % of the vocabulary cards, blocks reviewed release. The renderer splits each paragraph into sentences (one audio clip each) after `.`, `!`, `?`, `…` or `؟` before a letter that can start a sentence (the profile's `sentence_start`: a capital in German; also ¿ ¡ in Spanish), a digit, quotation mark or dash (a dialogue dash only before such a letter), and in a language without spaces after 。！？; but not after a single letter (*z. B.*), a day number (*am 3. Mai*) or one of the profile's `abbreviations`. See [story-writing.md](story-writing.md).

All content is plain text. The renderer escapes it and inserts `mark` around exact target spans. Examples have one clear primary target; embedded realizations are visible but need not receive a second highlight.

## Review

```json
{
  "schema_version": 2,
  "lesson_id": "L12",
  "inventory_sha256": "hash of inventory bytes",
  "lesson_sha256": "hash of lesson bytes",
  "reviewer": "reviewer identity",
  "method": "independent-source-comparison",
  "checks": {
    "source_inspection": "pass",
    "selection_quality": "pass",
    "vocabulary_quality": "pass",
    "grammar_accuracy": "pass",
    "redemittel_value": "pass",
    "example_integration": "pass",
    "compression": "pass"
  },
  "findings": [],
  "scope_note": "Print scope reviewed; missing audio remains outside the claim."
}
```

Use `independent-source-comparison` when a separate reviewer actually compared the exact source/inventory/lesson. Otherwise use `author-second-pass`. Findings are `{id, severity, issue, status, resolution}`; omit `resolution` only while `status` is `open`. A failed/not-checked check or open finding blocks reviewed release. Hashes bind review to exact inputs. A lesson with a story needs an eighth check, `"story_quality": "pass"`.

## Renderer behavior

`study_pack.py render` writes one HTML file and no evidence sidecar. Without an accepted review, pass `--draft` and use an output filename containing `DRAFT`. The renderer records status in a non-visible meta element. Its header shows only level, unit id and title. It never renders the source's name, inventory, source locations, review notes, dependencies or exclusions.

Mechanical validation checks structure, mappings, examples, exact embedded realizations, story coverage, private terms, hashes and review freshness. It also prints review notes (never blockers) for very short examples, examples that repeat six or more words of the inventory's evidence quotes, too many examples starting with *Ich*, and verb cards without a Perfekt. With the source's text (a PDF read through `pymupdf`, or `--source-text pages.txt`), it also reports every example and story paragraph that shares a run of six words with the source (twelve characters in a language without spaces), unless the run is mostly the card's own target or the story's declared form. It cannot decide whether selection or German is pedagogically good; semantic review must do that.

Whole-book course maps remain internal. They ensure every relevant lesson/module/reference page was inspected before a full-book claim; they are not learner deliverables.
