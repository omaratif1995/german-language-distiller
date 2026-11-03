# Spanish sample course

Two short lessons with **original example content** written for this repository: *En el mercado* (object pronouns *lo, la, los, las*) and *Un piso nuevo* (comparisons with *más … que* and *tan … como*). They show the skill with a language other than German, using the Spanish language profile (`skills/language-distiller/languages/es.json`). The Spanish was reviewed by its author, not yet by a native speaker.

- `S1_Studysheet_v1.html`, `S2_Studysheet_v1.html`: the reviewed study sheets, with the Spanish section names *Vocabulario*, *Gramática*, *Expresiones útiles* and *Historia*, and *el* and *la* in the masculine and feminine colours.
- `Curso_de_ejemplo_v1.html`: the study app built from them, without audio. A course in any language other than German speaks English to the learner (*Learn*, *Practise*, *Play*); the article game is *El · La*.
- `_work/`: the inventory, lesson data and review behind each sheet, `course.json`, and `narration.json` with the grammar explanations: one in simple Spanish, which the app plays and writes on the grammar card, and an English backup behind the EN button, with every Spanish word marked «…».
- `source/lecciones.md`: the stand-in "book" text.

To rebuild everything, run `python make_sample.py`. It uses `build()` from the German sample's `make_sample.py` with the Spanish settings.
