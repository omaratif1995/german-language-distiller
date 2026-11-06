"""Offline tests for course_audio.py (planning only) and build_course_app.py."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

import study_pack as pack
import course_audio
import build_course_app
import speech

NEEDS_DICTS = unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")


def tiny_story(word, frame):
    stem = frame.replace(" …", "")
    return {"title": "Ein langer Tag", "paragraphs": [
        {"de": f"Hier ist der {word}. Alle warten schon.", "en": "Here it is. Everyone is already waiting.",
         "uses": [{"card": "v1", "form": word}]},
        {"de": "Trotz des Regens gehen wir los. Es wird ein langer Tag.", "en": "Despite the rain we set off. It will be a long day.",
         "uses": [{"card": "g1", "form": "Trotz des Regens"}]},
        {"de": f"Am Abend sage ich: {stem}, ob wir morgen frei haben. Alle lachen.",
         "en": "In the evening I say: I wanted to ask whether we have tomorrow off. Everyone laughs.",
         "uses": [{"card": "e1", "form": stem}]}]}


def bundle(root, lesson_id, title, word, article, grammar_title, frame, story=False):
    """A tiny valid reviewed lesson, rendered with the normal sheet renderer."""
    source = root / "source.txt"
    if not source.exists():
        source.write_text("synthetic course source", encoding="utf-8")
    src = [{"pdf_index": 0, "region": "p0", "evidence": "synthetic"}]
    inventory = {
        "schema_version": 2, "lesson_id": lesson_id, "book": "Synthetic", "source_sha256": pack.file_hash(source),
        "scope_label": "synthetic", "scope_pages": [0],
        "pages": [{"pdf_index": 0, "folio": "1", "regions": [
            {"id": "p0", "label": "all", "status": "reviewed", "method": "text", "note": "synthetic"}]}],
        "items": [
            {"id": "i1", "kind": "vocabulary", "label": word, "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "v1", "reason": "test"},
            {"id": "i2", "kind": "grammar", "label": grammar_title, "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "g1", "reason": "test"},
            {"id": "i3", "kind": "expression", "label": frame, "importance": "essential", "sources": copy.deepcopy(src),
             "decision": "standalone", "home": "e1", "reason": "test"}],
        "dependencies": []}
    lesson = {
        "schema_version": 2, "lesson_id": lesson_id, "inventory_sha256": "0" * 64, "title": title, "level": "B1",
        "target_language": "de", "gloss_language": "en",
        "vocabulary": [{"id": "v1", "group": "Gruppe", "lemma": word, "pos": "noun", "article": article,
                        "forms": "Plural: –", "gloss": "test word",
                        "examples": [{"de": f"Hier ist {article} {word}.", "en": "Here it is.", "targets": [word]}]}],
        "grammar": [{"id": "g1", "title": grammar_title, "meaning": "A meaning.", "rule": "A rule.",
                     "patterns": [{"label": "pattern", "form": "A + B"}], "contrast": "A contrast.",
                     "examples": [{"de": "Trotz des Regens gehen wir.", "en": "Despite the rain we go.", "targets": ["Trotz des Regens"]},
                                  {"de": "Trotz der Kälte bleiben wir.", "en": "Despite the cold we stay.", "targets": ["Trotz der Kälte"]}]}],
        "redemittel": [{"id": "e1", "group": "Gruppe", "frame": frame, "gloss": "a frame", "when": "Use it.",
                        "variants": [{"form": "Variante …", "usage": "same"}],
                        "examples": [{"de": f"{frame.replace(' …', '')} heute.", "en": "today.", "targets": [frame.replace(" …", "")]}]}]}
    review = {"schema_version": 2, "lesson_id": lesson_id, "inventory_sha256": "0" * 64, "lesson_sha256": "0" * 64,
              "reviewer": "synthetic", "method": "independent-source-comparison",
              "checks": dict.fromkeys(pack.CHECKS, "pass"), "findings": [], "scope_note": "synthetic"}
    if story:
        lesson["story"] = tiny_story(word, frame)
        review["checks"][pack.STORY_CHECK] = "pass"
    paths = {name: root / f"{lesson_id}_{name}_v2.json" for name in ("Inventory", "Lesson", "Review")}
    paths["Inventory"].write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    lesson["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    paths["Lesson"].write_text(json.dumps(lesson, ensure_ascii=False), encoding="utf-8")
    review["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    review["lesson_sha256"] = pack.file_hash(paths["Lesson"])
    paths["Review"].write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    loaded = pack.validate_bundle(paths["Inventory"], paths["Lesson"], paths["Review"], source)
    sheet = root / f"{lesson_id}_Studysheet_v1.html"
    pack.render_files(loaded, sheet)
    return paths["Lesson"], sheet


class CourseAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        units = []
        for uid, title, word, art, gt, frame in (("U1", "Erste Einheit", "Termin", "der", "trotz + Genitiv", "Ich wollte fragen …"),
                                                 ("U2", "Zweite Einheit", "Ausflug", "der", "wegen + Genitiv", "Wie wäre es mit …")):
            lesson, sheet = bundle(self.root, uid, title, word, art, gt, frame, story=uid == "U1")
            units.append({"id": uid, "label": f"Einheit {uid[1:]}", "lesson": lesson.name, "sheet": sheet.name})
        self.course_path = self.root / "course.json"
        self.course_path.write_text(json.dumps({"title": "Test Kurs", "cache": "_work/audio", "units": units}), encoding="utf-8")

    @NEEDS_DICTS
    def test_plan_is_offline_and_deterministic(self):
        course = course_audio.load_course(self.course_path)
        clips, plan = course_audio.build_course_plan(course)
        again = course_audio.build_course_plan(course_audio.load_course(self.course_path))[1]
        self.assertEqual(plan, again)
        self.assertTrue((course["cache"] / "plan.json").is_file())
        unit = plan["units"]["U1"]
        for key in ("v1-head", "v1-ex-0", "g1-ex-0", "e1-head", "e1-variant-0", "e1-ex-0"):
            self.assertIn(key, unit["controls"])
        self.assertEqual(len(unit["explain"]["g1"]), 5)   # title, meaning, rule, one pattern, contrast
        self.assertEqual(len(course_audio.missing(course, clips)), len(clips))  # nothing synthesized offline

    @NEEDS_DICTS
    def test_narration_replaces_the_generated_explanation(self):
        (self.root / "narration.json").write_text(json.dumps(
            {"U1": {"g1": "Use «trotz» when something happens anyway. It takes the Genitiv: «trotz des Regens»."}}), encoding="utf-8")
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "narration": "narration.json"}), encoding="utf-8")
        course = course_audio.load_course(self.course_path)
        clips, plan = course_audio.build_course_plan(course)
        chain = plan["units"]["U1"]["explain"]["g1"]
        self.assertEqual(len(chain), 1)                    # the authored explanation names its topic itself
        self.assertNotIn(plan["units"]["U1"]["controls"]["g1-head"], plan["units"]["U1"]["sequence"])
        self.assertEqual(len(plan["units"]["U2"]["explain"]["g1"]), 5)
        parts = clips[chain[0]].parts
        self.assertIn(("de", "trotz des Regens."), parts)
        self.assertTrue(all(lang == "en" for lang, text in parts if "anyway" in text or "takes the" in text))
        # one teacher explains: the narrator speaks both languages, a little slower
        self.assertEqual(set(dict(clips[chain[0]].voices).values()), {"de-DE-SeraphinaMultilingualNeural"})
        self.assertEqual(clips[chain[0]].rate, "-15%")

    def test_a_german_explanation_with_an_english_backup(self):
        (self.root / "narration.json").write_text(json.dumps({"U1": {"g1": {
            "de": "Trotz heißt: Es passiert, aber es ist egal. Hör zu: Trotz des Regens gehen wir.",
            "en": "When something happens anyway, German says: «trotz.» It takes the Genitiv: «trotz des Regens.»"}}}),
            encoding="utf-8")
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "narration": "narration.json"}), encoding="utf-8")
        course = course_audio.load_course(self.course_path)
        clips, plan = course_audio.build_course_plan(course)
        unit = plan["units"]["U1"]
        german, english = clips[unit["explain"]["g1"][0]], clips[unit["explain_en"]["g1"][0]]
        self.assertEqual([lang for lang, _ in german.parts], ["de"])          # one request, so it flows like speech
        self.assertEqual(english.parts[1], ("de", "trotz."))
        self.assertEqual({german.rate, english.rate}, {"-15%"})
        self.assertTrue(german.timed and english.timed)                      # the card reads along with both
        self.assertIn(german.clip_id, unit["sequence"])                       # the lesson's listening plays German
        self.assertNotIn(english.clip_id, unit["sequence"])
        out = self.root / "app.html"
        build_course_app.build(course, out, audio=True, placeholder_audio=True)
        page = out.read_text(encoding="utf-8")
        self.assertIn(f'class="explain-button explain-en" data-chain="{english.clip_id}"', page)
        self.assertIn(f'class="explain-button" data-chain="{german.clip_id}"', page)

    def written_course(self):
        (self.root / "narration.json").write_text(json.dumps({"U1": {"g1": {
            "title": "trotz + Genitiv – der Gegensatz",
            "de": "Mit «trotz» sagst du: Es passiert, aber es ist egal. Hör zu:\n> Trotz des Regens gehen wir.\n"
                  "! Aber Vorsicht: Nach «trotz» kommt der Genitiv, «trotz des Regens».",
            "en": "When something happens anyway, German says: «trotz.» Listen:\n> «Trotz des Regens gehen wir.»",
            "patterns": [{"label": "Muster", "form": "trotz + Genitiv"}]}}}), encoding="utf-8")
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "narration": "narration.json"}), encoding="utf-8")
        return course_audio.load_course(self.course_path)

    def test_the_card_shows_the_explanation_written_out(self):
        course = self.written_course()
        clips, plan = course_audio.build_course_plan(course)
        german = clips[plan["units"]["U1"]["explain"]["g1"][0]]
        self.assertEqual(german.parts, (("de", "Mit trotz sagst du: Es passiert, aber es ist egal. Hör zu: Trotz des Regens "
                                               "gehen wir. Aber Vorsicht: Nach trotz kommt der Genitiv, trotz des Regens."),))
        out = self.root / "app.html"
        build_course_app.build(course, out, audio=True, placeholder_audio=True)
        page = out.read_text(encoding="utf-8")
        card = re.search(r'<article class="rule" id="U1-g1">(.*?)</article>', page, re.S).group(1)
        self.assertIn("<h3>trotz + Genitiv – der Gegensatz<button", card)      # the card speaks German
        self.assertIn(f'<div class="say" lang="de" data-clip="{german.clip_id}">', card)
        self.assertIn('<p class="say-p"><span class="sn">Mit <em class="g">trotz</em> sagst du:', card)
        self.assertIn('<div class="say-ex"><p><span class="sn">Trotz des Regens gehen wir.</span></p></div>', card)
        self.assertIn('<p class="say-warn">', card)
        self.assertIn('<em class="x">trotz des Regens</em>', card)            # a longer piece reads like an example
        self.assertIn("<summary>Auf Englisch</summary>", card)
        self.assertIn("<b>Muster:</b> trotz + Genitiv", card)
        for english in ("Meaning:", "Rule:", "Important:", "<b>pattern:</b>"):
            self.assertNotIn(english, card)
        other = re.search(r'<article class="rule" id="U2-g1">(.*?)</article>', page, re.S).group(1)
        self.assertIn("<b>Meaning:</b>", other)                               # a card without narration stays as it was
        cards = json.loads(re.search(r"CARDS=(\[.*?\]), ORDER=", page, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual(cards[1]["f"], "trotz + Genitiv – der Gegensatz")     # Üben asks with the German title

    def test_without_audio_the_explanation_is_still_written(self):
        out = self.root / "app.html"
        build_course_app.build(self.written_course(), out, audio=False)
        card = re.search(r'<article class="rule" id="U1-g1">(.*?)</article>', out.read_text(encoding="utf-8"), re.S).group(1)
        self.assertIn('<div class="say" lang="de">', card)
        self.assertNotIn("data-clip", card)

    def test_each_sentence_knows_when_it_is_spoken(self):
        cache = self.root / "cache"
        (cache / "clips").mkdir(parents=True)
        spoken = [(0.05, "Hör"), (0.4, "zu"), (1.3, "Trotz"), (1.7, "des"), (1.9, "Regens"), (2.5, "gehen"), (2.8, "wir")]
        (cache / "clips" / "a_test.words.json").write_text(json.dumps(spoken), encoding="utf-8")
        shown = build_course_app.explanation_html("«Hör» zu:\n> Trotz des Regens gehen wir.", "de", None, "a_test", cache)
        self.assertEqual(re.findall(r'data-at="([\d.]+)"', shown), ["0.05", "1.30"])
        self.assertIn('<em class="g">Hör</em>', shown)
        self.assertIn('data-clip="a_test"', shown)

    def test_narration_must_be_a_text_or_de_and_en(self):
        (self.root / "narration.json").write_text(json.dumps({"U1": {"g1": {"fr": "Non."}}}), encoding="utf-8")
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "narration": "narration.json"}), encoding="utf-8")
        with self.assertRaisesRegex(course_audio.AudioError, "narration U1 g1"):
            course_audio.narration_notes(course_audio.load_course(self.course_path))

    def test_written_narration_is_checked(self):
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "narration": "narration.json"}), encoding="utf-8")
        for told, error in (({"de": "Mit «trotz sagst du es."}, "close in turn"),
                            ({"de": "Text.", "patterns": [{"label": "Muster"}]}, "patterns")):
            (self.root / "narration.json").write_text(json.dumps({"U1": {"g1": told}}), encoding="utf-8")
            with self.assertRaisesRegex(course_audio.AudioError, error):
                course_audio.narration_notes(course_audio.load_course(self.course_path))
        (self.root / "narration.json").write_text(json.dumps({"U1": {"g1": {
            "de": "Text.", "en": "Listen:\n> «Trotz des Regens» we go."}}}), encoding="utf-8")
        notes = course_audio.narration_notes(course_audio.load_course(self.course_path))
        self.assertTrue(any("English example line" in note for note in notes))

    def test_app_without_audio(self):
        out = self.root / "app.html"
        result = build_course_app.build(course_audio.load_course(self.course_path), out, audio=False)
        page = out.read_text(encoding="utf-8")
        self.assertEqual(result["cards"], 6)
        self.assertEqual(page.count('<section class="unit"'), 2)
        self.assertIn('id="practice"', page)
        self.assertNotIn('class="speak-button"', page)
        self.assertNotIn('class="listen-all"', page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        cards = json.loads(re.search(r"CARDS=(\[.*?\]), ORDER=", page, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual([c["k"] for c in cards], ["w", "g", "r", "w", "g", "r"])
        self.assertEqual({c["id"] for c in cards}, {"U1-v1", "U1-g1", "U1-e1", "U2-v1", "U2-g1", "U2-e1"})
        self.assertNotIn("<button", cards[1]["f"], "grammar front must not contain the audio button")
        self.assertEqual([c["a"] for c in cards[:3]], ["der Termin = test word", "trotz + Genitiv", "Ich wollte fragen …"])
        for action in ('data-a="good"', 'data-a="again"', 'data-a="go"', 'id="undo"'):
            self.assertIn(action, page)
        self.assertNotIn('id="skip"', page)

    @NEEDS_DICTS
    def test_app_audio_controls_with_placeholder_payloads(self):
        out = self.root / "app_audio.html"
        build_course_app.build(course_audio.load_course(self.course_path), out, audio=True, placeholder_audio=True)
        page = out.read_text(encoding="utf-8")
        self.assertEqual(page.count('class="listen-open"'), 2)       # 🎧 Anhören opens the listening panel
        self.assertEqual(page.count('class="explain-button"'), 2)
        self.assertGreaterEqual(page.count('class="speak-button"'), 10)
        self.assertEqual(page.count('class="story-play"'), 1)
        self.assertEqual(page.count('class="speak-button para-play"'), 3)   # one 🔊 per story paragraph (U1 only)
        self.assertEqual(page.count('class="ss" id="U1-story-s'), 6)
        self.assertEqual(len(re.findall(r'class="ss" id="U1-story-s\d+" data-audio="a_', page)), 6)
        self.assertIn('data-m="ex"', page)                           # Nur Beispiele
        self.assertNotIn('type="text/plain" id="au-', page)   # placeholder: no payload blocks
        self.assertLess(page.index("<script>", page.rindex("</main>")), page.rindex("</main>") + 20)   # after the units
        sequences = {name: json.loads(re.search(name + r"=(\{.*?\}), ", page, re.S).group(1)) for name in ("SEQ", "EXS", "STO")}
        self.assertEqual([step[2] for step in sequences["EXS"]["U1"]], ["U1-v1-x0", "U1-g1-x0", "U1-g1-x1", "U1-e1-x0"])
        self.assertEqual(sequences["STO"]["U2"], [])
        explain = [step for step in sequences["SEQ"]["U1"] if step[2] == "U1-g1" and not step[3]]
        self.assertTrue(explain and all(step[1] == 0.4 for step in explain))   # a breath after the spoken explanation
        self.assertEqual(sequences["STO"]["U1"][0][2], "U1-story")
        self.assertEqual(len(sequences["STO"]["U1"]), 7)               # title + six sentences

    def test_games_and_story_are_built_from_the_lesson_data(self):
        out = self.root / "app_games.html"
        build_course_app.build(course_audio.load_course(self.course_path), out, audio=False)
        page = out.read_text(encoding="utf-8")
        self.assertIn('id="tab-g"', page)
        for name in ("Hör-Bingo", "Wortpaare", "Satzbau", "Der · Die · Das", "Was sagt man?"):
            self.assertIn(name, page)
        games = json.loads(re.search(r", G=(\{.*?\});\n", page, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual(games["U1"]["v"][0]["a"], "der")
        self.assertEqual(games["U1"]["v"][0]["x"][0]["t"], [[13, 19]])    # «Termin» in «Hier ist der Termin.»
        self.assertEqual([s["de"] for s in games["U1"]["s"]],               # Satzbau: the plain sentences of 5–9 words
                         ["Trotz des Regens gehen wir.", "Trotz der Kälte bleiben wir."])
        self.assertEqual(games["U2"]["r"][0]["f"], "Wie wäre es mit …")
        self.assertIn('class="lw" data-card="v1"', page)                   # underlined story word with its meaning
        self.assertIn('id="U1-v1-x0"', page)

    def test_article_game_accepts_both_articles_of_adjective_nouns(self):
        def card(lemma, article, forms):
            return {"lemma": lemma, "article": article, "forms": forms}
        accepted = build_course_app.accepted_articles
        self.assertEqual(accepted(card("Bekannte", "der", "die Bekannte · ein Bekannter · Plural: die Bekannten")), ["der", "die"])
        self.assertEqual(accepted(card("Joghurt", "der", "der or das Joghurt · Plural: die Joghurts")), ["der", "das"])
        self.assertEqual(accepted(card("Ansicht", "die", "Plural: die Ansichten · der Ansicht sein, dass …")), ["die"])
        self.assertEqual(accepted(card("Zweifel", "der", "Plural: die Zweifel · Zweifel haben")), ["der"])
        self.assertIn("(cur_.aa||[cur_.a]).indexOf(a)>=0", build_course_app.APP_JS)

    def test_bingo_knows_which_unit_words_each_example_holds(self):
        def card(lemma, sentence, *targets):
            return {"id": lemma[:4], "lemma": lemma, "gloss": "-", "examples": [{"de": sentence, "en": "-", "targets": list(targets)}]}
        lesson = {"vocabulary": [card("Bahnhof", "Wir treffen uns am Bahnhof neben dem Kiosk.", "Bahnhof"),
                                 card("Kiosk", "Am Kiosk kaufe ich jeden Morgen eine Zeitung.", "Kiosk"),
                                 card("sich beeilen", "Ich beeile mich, sonst verpasse ich den Zug.", "beeile", "mich"),
                                 card("verpassen", "Gestern haben wir den Bus verpasst.", "verpasst")],
                  "grammar": [], "redemittel": []}
        words = build_course_app.game_data(lesson)["v"]
        # a call for «Bahnhof» also holds «Kiosk», so Hör-Bingo never calls it while both are on the card;
        # «verpasse» is a form of «verpassen» even though the lesson only marks «verpasst»; «mich» is not a word of its own
        self.assertEqual([w["x"][0]["m"] for w in words], [[1], [], [3], []])

    def test_satzbau_takes_plain_sentences_of_five_to_nine_words(self):
        ok = build_course_app.puzzle_sentence
        self.assertTrue(ok("Am Samstag backe ich mit meiner Tochter Brot."))
        self.assertFalse(ok("Hier ist der Termin."))                                          # too short to be a puzzle
        self.assertFalse(ok("Betreff: Anfrage wegen der Wohnung im zweiten Stock"))           # a heading, not a sentence
        self.assertFalse(ok("Das kenne ich gut: Ich verliere ständig meine Schlüssel."))      # two sentences in one
        self.assertFalse(ok("Am Sonntag besuchen wir mit den Kindern die Großeltern auf ihrem Bauernhof."))   # over nine words

    def test_books_in_one_course_are_grouped(self):
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        for unit, book in zip(data["units"], ("Buch 1", "Buch 2")):
            unit["group"] = book
        self.course_path.write_text(json.dumps(data), encoding="utf-8")
        out = self.root / "app_books.html"
        build_course_app.build(course_audio.load_course(self.course_path), out, audio=False)
        page = out.read_text(encoding="utf-8")
        self.assertIn('<optgroup label="Buch 1"><option value="U1">', page)       # the lesson picker, book by book
        self.assertIn('<optgroup label="Buch 2"><option value="U2">', page)
        config = json.loads(re.search(r"CFG=(\{.*?\}), G=", page, re.S).group(1))
        self.assertEqual(config["groups"], [["Buch 1", ["U1"]], ["Buch 2", ["U2"]]])   # one chip per book in Üben

    def test_units_without_books_keep_a_plain_picker(self):
        out = self.root / "app_plain.html"
        build_course_app.build(course_audio.load_course(self.course_path), out, audio=False)
        page = out.read_text(encoding="utf-8")
        self.assertNotIn("<optgroup", page)
        self.assertNotIn('"groups"', page)

    def test_a_book_is_one_run_of_units(self):
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        data["units"][0]["group"] = "Buch 1"
        self.course_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "every unit a group, or none"):
            course_audio.load_course(self.course_path)
        data["units"] = data["units"] + [dict(data["units"][0], id="U3")]
        data["units"][1]["group"], data["units"][2]["group"] = "Buch 2", "Buch 1"
        self.course_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "must follow each other"):
            course_audio.load_course(self.course_path)

    def test_other_units_are_hidden_before_the_page_reads_them(self):
        out = self.root / "app_early.html"
        build_course_app.build(course_audio.load_course(self.course_path), out, audio=False)
        page = out.read_text(encoding="utf-8")
        head = page[:page.index("</head>")]
        self.assertIn("r.classList.add('js')", head)                  # .js .unit{display:none} holds from the first unit on
        self.assertIn("localStorage.getItem('test-kurs:ui')", head)   # the unit the learner was on shows at once
        self.assertIn('?u.unit:\'U1\'', head)
        self.assertLess(page.index("</head>"), page.index('<section class="unit"'))
        bar = page[page.index("</nav>"):page.index('<section class="unit"')]       # the bar shows the tab and unit at once
        self.assertIn("localStorage.getItem('test-kurs:ui')", bar)
        self.assertIn("d.body.classList.add(t==='p'?'mode-practice':'mode-games')", bar)

    def test_unknown_course_key_is_refused(self):
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "episodes_out": "../Audio"}), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "unknown key.*episodes_out"):
            course_audio.load_course(self.course_path)

    def test_listening_engine_names_do_not_clash_with_the_app(self):
        # Both scripts share one function scope; a later declaration with the same name silently replaces the engine's.
        def top_level_functions(js):
            return set(re.findall(r"^  function ([A-Za-z_$][\w$]*)\(", js, re.M))
        engine = top_level_functions(build_course_app.LISTEN_JS)
        app = top_level_functions(build_course_app.APP_JS.replace("__LISTEN__", ""))
        self.assertTrue(engine and app)
        self.assertEqual(engine & app, set())

    def test_private_terms_keep_the_source_name_out(self):
        data = json.loads(self.course_path.read_text(encoding="utf-8"))
        self.course_path.write_text(json.dumps({**data, "private_terms": ["Test"]}), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "private source term"):
            course_audio.load_course(self.course_path)
        self.course_path.write_text(json.dumps({**data, "private_terms": ["Termin"]}), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "private source term"):
            build_course_app.build(course_audio.load_course(self.course_path), self.root / "leak.html", audio=False)

    @NEEDS_DICTS
    def test_explanations_are_not_counted_as_german_clips(self):
        course = course_audio.load_course(self.course_path)
        unit_plan = course_audio.build_course_plan(course)[1]["units"]["U1"]
        unit = course["units"][0]
        used = set()
        build_course_app.add_audio_buttons(unit["sheet"].read_text(encoding="utf-8"),
                                           json.loads(unit["lesson"].read_text(encoding="utf-8")), unit_plan, used)
        self.assertTrue(used)
        self.assertFalse(used & set(unit_plan["explain"]["g1"]), "explanations get the smaller explain bitrate")

    def test_refuses_overwrite_and_unreviewed_sheets(self):
        out = self.root / "app.html"
        out.write_text("x", encoding="utf-8")
        self.assertEqual(build_course_app.main(["--course", str(self.course_path), "--output", str(out), "--no-audio"]), 1)
        sheet = self.root / "U1_Studysheet_v1.html"
        sheet.write_text(sheet.read_text(encoding="utf-8").replace('content="reviewed"', 'content="draft"'), encoding="utf-8")
        with self.assertRaises(Exception):
            build_course_app.build(course_audio.load_course(self.course_path), self.root / "app2.html", audio=False)


if __name__ == "__main__":
    unittest.main()
