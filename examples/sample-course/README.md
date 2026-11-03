# Sample course

Two short lessons with **original example content** written for this repository: *Der erste Arbeitstag* and *Pläne fürs Wochenende*. They show what the skill produces without using any commercial book.

- `E1_Studysheet_v1.html`, `E2_Studysheet_v1.html`: the reviewed study sheets.
- `Sample_Studienpaket_v1.html`: the study app built from them, without audio. Open it in a browser, then try *Üben*.
- `_work/`: the structured data behind each sheet, made of the inventory (what was found and why it was kept or dropped), the lesson data and the review. `course.json` lists the units for the app. `narration.json` holds the grammar explanations: one in simple German, which the app plays and writes on the grammar card (it lights up the sentence being spoken), and an English backup behind the EN button, with every German word marked «…».
- `source/sample-lessons.md`: the stand-in "book" text.

To rebuild everything, run `python make_sample.py`. To add audio, run `course_audio.py synth` and then `build_course_app.py` without `--no-audio` (see the skill's `references/course-app.md`).
