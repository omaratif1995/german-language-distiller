"""Language profiles: German keeps its own texts, every app text is translated, and Spanish, Arabic (right to left)
and Japanese (no spaces between words) courses are built end to end."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

import build_course_app
import course_audio
import embed_audio
import language
import speech
import study_pack as pack
import validate_study_pack

NEEDS_DICTS = unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")
def validates(sheet):
    """The sheet passes the HTML validator (its report stays out of the test output)."""
    with contextlib.redirect_stdout(io.StringIO()):
        return validate_study_pack.main([str(sheet)]) == 0


TEMPLATES = (build_course_app.APP_JS + build_course_app.PRACTICE + build_course_app.GAMES + build_course_app.FRAME
             + embed_audio.LISTEN_JS + embed_audio.LISTEN_HTML)


def write_lesson(root, lesson):
    """Render a reviewed lesson with the normal sheet renderer, with an inventory and a review made to fit it."""
    source = root / "source.txt"
    source.write_text("synthetic course source", encoding="utf-8")
    src = [{"pdf_index": 0, "region": "p0", "evidence": "synthetic"}]
    kinds = {"vocabulary": "vocabulary", "grammar": "grammar", "redemittel": "expression"}
    cards = [(section, record) for section in kinds for record in lesson[section]]
    lesson_id = lesson["lesson_id"]
    inventory = {
        "schema_version": 2, "lesson_id": lesson_id, "book": "Synthetic", "source_sha256": pack.file_hash(source),
        "scope_label": "synthetic", "scope_pages": [0],
        "pages": [{"pdf_index": 0, "folio": "1", "regions": [
            {"id": "p0", "label": "all", "status": "reviewed", "method": "text", "note": "synthetic"}]}],
        "items": [{"id": f"i{n}", "kind": kinds[section], "label": record.get("lemma") or record.get("title") or record["frame"],
                   "importance": "essential", "sources": copy.deepcopy(src), "decision": "standalone", "home": record["id"],
                   "reason": "test"} for n, (section, record) in enumerate(cards, 1)],
        "dependencies": []}
    lesson = dict(lesson, schema_version=2, inventory_sha256="0" * 64)
    review = {"schema_version": 2, "lesson_id": lesson_id, "inventory_sha256": "0" * 64, "lesson_sha256": "0" * 64,
              "reviewer": "synthetic", "method": "independent-source-comparison",
              "checks": {**dict.fromkeys(pack.CHECKS, "pass"), pack.STORY_CHECK: "pass"}, "findings": [], "scope_note": "synthetic"}
    paths = {name: root / f"{lesson_id}_{name}_v2.json" for name in ("Inventory", "Lesson", "Review")}
    paths["Inventory"].write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    lesson["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    paths["Lesson"].write_text(json.dumps(lesson, ensure_ascii=False), encoding="utf-8")
    review["inventory_sha256"] = pack.file_hash(paths["Inventory"])
    review["lesson_sha256"] = pack.file_hash(paths["Lesson"])
    paths["Review"].write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    bundle = pack.validate_bundle(paths["Inventory"], paths["Lesson"], paths["Review"], source)
    sheet = root / f"{lesson_id}_Studysheet_v1.html"
    pack.render_files(bundle, sheet)
    return paths["Lesson"], sheet


def build_app(root, lesson, sheet):
    """The study app of a one-unit course, without audio, and the data of its games."""
    course = root / "course.json"
    course.write_text(json.dumps({"title": "Test", "units": [{"id": "U1", "label": "1", "lesson": lesson.name, "sheet": sheet.name}]}),
                      encoding="utf-8")
    out = root / "app.html"
    build_course_app.build(course_audio.load_course(course), out, audio=False)
    app = out.read_text(encoding="utf-8")
    return app, json.loads(re.search(r", G=(\{.*?\});\n", app, re.S).group(1).replace("<\\/", "</"))["U1"]


def spanish_lesson(root, lesson_id="S1", target="es", article="el"):
    """A tiny reviewed Spanish lesson with a story (`target` and `article` can turn it into a lesson of another
    profile, or one whose nouns carry no article)."""
    return write_lesson(root, {
        "lesson_id": lesson_id, "title": "En el mercado", "level": "A2", "target_language": target, "gloss_language": "en",
        "vocabulary": [{"id": "v1", "group": "Compras", "lemma": "mercado", "pos": "noun", **({"article": article} if article else {}),
                        "forms": "Plural: los mercados", "gloss": "market",
                        "examples": [{"de": "Los sábados compro fruta fresca en el mercado.", "en": "On Saturdays I buy fresh fruit at the market.",
                                      "targets": ["mercado"]}]}],
        "grammar": [{"id": "g1", "title": "ir a + infinitivo", "meaning": "A plan for the near future.", "rule": "ir in the present + a + infinitive.",
                     "patterns": [{"label": "pattern", "form": "voy / vas / va + a + infinitivo"}], "contrast": "Not the simple future.",
                     "examples": [{"de": "Mañana voy a cocinar para mis amigos.", "en": "Tomorrow I am going to cook for my friends.",
                                   "targets": ["voy a cocinar"]},
                                  {"de": "Este verano vamos a viajar a Perú.", "en": "This summer we are going to travel to Peru.",
                                   "targets": ["vamos a viajar"]}]}],
        "redemittel": [{"id": "e1", "group": "En el café", "frame": "Me gustaría …", "gloss": "I would like …",
                        "when": "Order or ask politely.", "variants": [{"form": "Quisiera …", "usage": "just as polite"}],
                        "examples": [{"de": "Me gustaría un café con leche, por favor.", "en": "I would like a white coffee, please.",
                                      "targets": ["Me gustaría"]}]}],
        "story": {"title": "Un sábado en el mercado", "paragraphs": [
            {"de": "Hoy Lucía va al mercado con su hermano. Compran tomates y pan.", "en": "Today Lucía goes to the market with her brother. They buy tomatoes and bread.",
             "uses": [{"card": "v1", "form": "mercado"}]},
            {"de": "Esta noche vamos a cocinar juntos, dice ella. La cocina es pequeña.", "en": "We are going to cook together tonight, she says. The kitchen is small.",
             "uses": [{"card": "g1", "form": "vamos a cocinar"}]},
            {"de": "En el café pide: Me gustaría un té verde. Su hermano se ríe.", "en": "In the café she asks: I would like a green tea. Her brother laughs.",
             "uses": [{"card": "e1", "form": "Me gustaría"}]}]}})


def word(card, lemma, pos, forms, gloss, sentence, english, target, group):
    return {"id": card, "group": group, "lemma": lemma, "pos": pos, "forms": forms, "gloss": gloss,
            "examples": [{"de": sentence, "en": english, "targets": [target]}]}


def phrase(card, group, frame, gloss, when, sentence, english, target, variants=()):
    return {"id": card, "group": group, "frame": frame, "gloss": gloss, "when": when, "variants": list(variants),
            "examples": [{"de": sentence, "en": english, "targets": [target]}]}


# Two small original lessons, written for these tests and not reviewed by a native speaker: Arabic is written right
# to left and joins small words to the next one (والفاكهة), Japanese puts no spaces between its words.
ARABIC = {
    "lesson_id": "A1", "title": "في السوق", "level": "A2", "target_language": "ar", "gloss_language": "en",
    "vocabulary": [
        word("v1", "سوق", "noun", "Plural: أسواق", "market", "أشتري الخضار من السوق كل يوم سبت.",
             "I buy vegetables at the market every Saturday.", "السوق", "التسوق"),
        word("v2", "خبز", "noun", "no plural", "bread", "نأكل الخبز الطازج مع الجبن في الصباح.",
             "We eat fresh bread with cheese in the morning.", "الخبز", "التسوق"),
        word("v3", "فاكهة", "noun", "Plural: فواكه", "fruit", "تحب أختي الفاكهة أكثر من الحلويات.",
             "My sister likes fruit more than sweets.", "الفاكهة", "التسوق"),
        word("v4", "سعر", "noun", "Plural: أسعار", "price", "سعر البرتقال اليوم مرتفع جدًا.",
             "The price of oranges is very high today.", "سعر", "التسوق"),
        word("v5", "بائع", "noun", "Plural: باعة", "seller", "البائع يبتسم ويعطينا كيسًا كبيرًا.",
             "The seller smiles and gives us a big bag.", "البائع", "التسوق"),
        word("v6", "رخيص", "adjective", "feminine: رخيصة", "cheap", "الطماطم رخيصة في نهاية الأسبوع.",
             "Tomatoes are cheap at the end of the week.", "رخيصة", "التسوق")],
    "grammar": [{"id": "g1", "title": "The future with سوف", "meaning": "Talk about what will happen.",
                 "rule": "سوف (or the short سـ) comes before a verb in the present tense.",
                 "patterns": [{"label": "pattern", "form": "سوف + أفعل / نفعل / تفعل"}],
                 "contrast": "سـ is the short form, joined to the verb: سأسافر. Some speakers keep it for the nearer future.",
                 "examples": [{"de": "سوف أسافر إلى القاهرة في الصيف.", "en": "I will travel to Cairo in the summer.", "targets": ["سوف أسافر"]},
                              {"de": "سوف نطبخ العشاء معًا الليلة.", "en": "We will cook dinner together tonight.", "targets": ["سوف نطبخ"]}]}],
    "redemittel": [
        phrase("e1", "في المقهى", "أريد …", "I want …", "Order or ask for something.", "أريد فنجان قهوة من فضلك.",
               "I would like a cup of coffee, please.", "أريد", [{"form": "أودّ …", "usage": "more polite"}]),
        phrase("e2", "في السوق", "كم سعر …؟", "How much is …?", "Ask for a price at the market.", "كم سعر هذا القميص الأزرق؟",
               "How much is this blue shirt?", "كم سعر"),
        phrase("e3", "في السوق", "شكرًا جزيلًا", "Thank you very much", "Thank someone warmly.", "شكرًا جزيلًا على مساعدتك اليوم.",
               "Thank you very much for your help today.", "شكرًا جزيلًا")],
    "story": {"title": "يوم السبت في السوق", "paragraphs": [
        {"de": "تذهب ليلى إلى السوق مع أخيها. يشتريان الخبز والفاكهة.",
         "en": "Layla goes to the market with her brother. They buy bread and fruit.",
         "uses": [{"card": "v1", "form": "السوق"}, {"card": "v2", "form": "الخبز"}, {"card": "v3", "form": "الفاكهة"}]},
        {"de": "البائع يقول: سعر التفاح منخفض اليوم. هل هذا صحيح؟ نعم، التفاح رخيص جدًا.",
         "en": "The seller says: the price of apples is low today. Is that true? Yes, the apples are very cheap.",
         "uses": [{"card": "v5", "form": "البائع"}, {"card": "v4", "form": "سعر"}, {"card": "v6", "form": "رخيص"}]},
        {"de": "سوف نطبخ معًا الليلة، تقول ليلى. وفي المقهى تقول: أريد شايًا أخضر.",
         "en": "We will cook together tonight, Layla says. And in the café she says: I would like a green tea.",
         "uses": [{"card": "g1", "form": "سوف نطبخ"}, {"card": "e1", "form": "أريد"}]}]}}

JAPANESE = {
    "lesson_id": "J1", "title": "市場で", "level": "A2", "target_language": "ja", "gloss_language": "en",
    "vocabulary": [
        word("v1", "市場", "noun", "いちば", "market", "毎週土曜日に市場で野菜を買います。",
             "Every Saturday I buy vegetables at the market.", "市場", "買い物"),
        word("v2", "パン", "noun", "", "bread", "朝はチーズとパンを食べます。", "In the morning I eat cheese and bread.", "パン", "買い物"),
        word("v3", "果物", "noun", "くだもの", "fruit", "妹はお菓子より果物が好きです。",
             "My younger sister likes fruit more than sweets.", "果物", "買い物"),
        word("v4", "値段", "noun", "ねだん", "price", "今日はオレンジの値段がとても高いです。",
             "Today the price of oranges is very high.", "値段", "買い物"),
        word("v5", "店員", "noun", "てんいん", "shop assistant", "あの店の店員はとても親切です。",
             "The shop assistant in that shop is very kind.", "店員", "買い物"),
        word("v6", "安い", "adjective", "やすい; past: 安かった", "cheap", "週末はトマトが安いです。",
             "Tomatoes are cheap at the weekend.", "安い", "買い物")],
    "grammar": [{"id": "g1", "title": "Plans with つもりです", "meaning": "Say what you plan to do.",
                 "rule": "Put つもりです after the dictionary form of the verb.",
                 "patterns": [{"label": "pattern", "form": "行く / 食べる / 料理する + つもりです"}],
                 "contrast": "For a plan you are only thinking about, 〜ようと思います is softer.",
                 "examples": [{"de": "夏に京都へ行くつもりです。", "en": "I plan to go to Kyoto in the summer.", "targets": ["行くつもりです"]},
                              {"de": "今夜は家で料理するつもりです。", "en": "Tonight I plan to cook at home.", "targets": ["料理するつもりです"]}]}],
    "redemittel": [
        phrase("e1", "喫茶店で", "〜をお願いします", "… please", "Order politely in a shop or café.", "コーヒーを一つお願いします。",
               "One coffee, please.", "お願いします", [{"form": "〜をください", "usage": "a little more direct"}]),
        phrase("e2", "市場で", "〜はいくらですか", "How much is …?", "Ask for a price.", "このシャツはいくらですか。",
               "How much is this shirt?", "いくらですか"),
        phrase("e3", "市場で", "どうもありがとうございます", "Thank you very much", "Thank someone warmly.",
               "手伝ってくださって、どうもありがとうございます。", "Thank you very much for helping me.", "どうもありがとうございます")],
    "story": {"title": "土曜日の市場", "paragraphs": [
        {"de": "さくらは弟と市場へ行きます。パンと果物を買います。",
         "en": "Sakura goes to the market with her younger brother. They buy bread and fruit.",
         "uses": [{"card": "v1", "form": "市場"}, {"card": "v2", "form": "パン"}, {"card": "v3", "form": "果物"}]},
        {"de": "店員は「今日はりんごが安いですよ」と言います。値段を見ると、本当に安いです。",
         "en": "The shop assistant says: apples are cheap today. When Sakura looks at the price, they really are cheap.",
         "uses": [{"card": "v5", "form": "店員"}, {"card": "v4", "form": "値段"}, {"card": "v6", "form": "安い"}]},
        {"de": "二人は今夜一緒に料理するつもりです。喫茶店で、さくらは「紅茶をお願いします」と言います。",
         "en": "The two of them plan to cook together tonight. In the café, Sakura says: a black tea, please.",
         "uses": [{"card": "g1", "form": "料理するつもりです"}, {"card": "e1", "form": "お願いします"}]}]}}


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(speech.use, language.profile("de"))      # speech keeps one language at a time
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_german_keeps_its_own_texts(self):
        german = language.profile("de-DE")
        self.assertEqual(language.ui_table(german), {})
        self.assertEqual(language.article_title(german), "Der · Die · Das")
        self.assertEqual(language.localize(TEMPLATES, language.ui_table(german)), TEMPLATES)

    def test_every_translated_text_is_still_in_the_app(self):
        sources = "".join(Path(module.__file__).read_text(encoding="utf-8")
                          for module in (build_course_app, embed_audio, course_audio))
        for german in language.UI_EN:
            self.assertRegex(sources, r"""['">]\s*""" + re.escape(german) + r"""\s*['"<]""", f"{german!r} is no longer in the app")

    def test_a_spanish_app_shows_no_german_text(self):
        spanish = language.localize(TEMPLATES, language.ui_table(language.profile("es")))
        for german in (key for key, english in language.UI_EN.items() if english != key):     # «Pause» is English too
            self.assertNotRegex(spanish, r"""(?:'|>|=")\s*""" + re.escape(german) + r"""\s*(?:'|<|")""", german)
        self.assertIn("'Listening Bingo'", spanish)
        self.assertIn("'Build the Spanish sentence: tap the words in order.'", spanish)

    def test_a_spanish_course_end_to_end(self):
        lesson, sheet = spanish_lesson(self.root)
        page = sheet.read_text(encoding="utf-8")
        self.assertIn('<html lang="es">', page)
        for title in ("Vocabulario", "Gramática", "Expresiones útiles", "Historia", "Traducción"):
            self.assertIn(title, page)
        self.assertIn('<span class="art-der">el</span> mercado', page)      # «el» borrows the masculine colour
        self.assertTrue(validates(sheet))
        course = self.root / "course.json"
        course.write_text(json.dumps({"title": "Curso de prueba", "units": [
            {"id": "S1", "label": "Unidad 1", "lesson": lesson.name, "sheet": sheet.name}]}), encoding="utf-8")
        loaded = course_audio.load_course(course)
        self.assertEqual((loaded["profile"]["code"], loaded["voices"]["de"]), ("es", "es-ES-ElviraNeural"))
        out = self.root / "app.html"
        build_course_app.build(loaded, out, audio=False)
        app = out.read_text(encoding="utf-8")
        self.assertIn('<html lang="es">', app)
        for english in (">Learn<", ">Practise<", ">Play<", "'Listening Bingo'", "'El · La'", "'Word Pairs'"):
            self.assertIn(english, app)
        for german in (">Lernen<", ">Spielen<", "'Hör-Bingo'", "'Der · Die · Das'"):
            self.assertNotIn(german, app)
        self.assertIn('"arts":["el","la"]', app)

    @NEEDS_DICTS
    def test_spanish_words_inside_english_are_spoken_in_spanish(self):
        speech.use(language.profile("es"))
        self.assertEqual(speech.segments("Use «mercado» for the market", "en"),
                         [("en", "Use "), ("de", "mercado"), ("en", " for the market")])
        clip = speech.make_clip("The word mañana means tomorrow.", "en", {"de": "es-ES-ElviraNeural", "en": "en-US-AvaNeural"})
        self.assertIn(("de", "mañana"), clip.parts)

    def test_a_language_without_articles(self):
        # nouns need no article there, the sheet shows none and the app offers no article game
        language._cache["xa"] = dict(language.profile("es"), code="xa", name="Testish", articles=[], article_colours={})
        self.addCleanup(language._cache.pop, "xa", None)
        lesson, sheet = spanish_lesson(self.root, target="xa", article=None)
        page = sheet.read_text(encoding="utf-8")
        self.assertIn('<html lang="xa">', page)
        self.assertIn('<span class="de">mercado</span>', page)
        self.assertTrue(validates(sheet))
        course = self.root / "course.json"
        course.write_text(json.dumps({"title": "Test", "units": [{"id": "S1", "label": "1", "lesson": lesson.name, "sheet": sheet.name}]}),
                          encoding="utf-8")
        out = self.root / "app.html"
        build_course_app.build(course_audio.load_course(course), out, audio=False)
        self.assertIn('"arts":[]', out.read_text(encoding="utf-8"))          # ARTS.length>1 fails: no article game

    def test_an_unknown_language_says_how_to_add_one(self):
        with self.assertRaisesRegex(language.LanguageError, r"languages/xx\.json.*available: ar, de, es, ja"):
            language.profile("xx-YY")

    def test_a_course_keeps_one_language(self):
        spanish, sheet = spanish_lesson(self.root)
        data = json.loads(spanish.read_text(encoding="utf-8"))
        german = self.root / "D1_Lesson_v2.json"
        german.write_text(json.dumps(dict(data, target_language="de")), encoding="utf-8")
        course = self.root / "course.json"
        course.write_text(json.dumps({"title": "Mixed", "units": [
            {"id": "S1", "label": "1", "lesson": spanish.name, "sheet": sheet.name},
            {"id": "D1", "label": "2", "lesson": german.name, "sheet": sheet.name}]}), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "one target language"):
            course_audio.load_course(course)

    def test_spanish_sentences_open_with_inverted_marks_dashes_and_accents(self):
        spanish = language.profile("es")
        self.assertEqual(pack.story_sentences("Llama enseguida: ¿Se puede visitar mañana? ¡Claro! Álvaro firma.", spanish),
                         ["Llama enseguida: ¿Se puede visitar mañana?", "¡Claro!", "Álvaro firma."])
        self.assertEqual(pack.story_sentences("—Me pone un kilo, por favor —dice Marta. —Están muy frescas.", spanish),
                         ["—Me pone un kilo, por favor —dice Marta.", "—Están muy frescas."])
        self.assertEqual(pack.story_sentences("El Sr. García llega tarde. Luego come.", spanish),
                         ["El Sr. García llega tarde.", "Luego come."])
        # a dialogue tag after ? or ! goes on with the same sentence; a new line of dialogue starts a new one
        self.assertEqual(pack.story_sentences("—Están muy frescas, ¡pruébelas! —contesta el vendedor. Marta prueba una.", spanish),
                         ["—Están muy frescas, ¡pruébelas! —contesta el vendedor.", "Marta prueba una."])

    def test_an_arabic_course_reads_right_to_left(self):
        lesson, sheet = write_lesson(self.root, ARABIC)
        page = sheet.read_text(encoding="utf-8")
        self.assertIn('<html lang="ar">', page)
        self.assertIn(pack.RTL_CSS, page)                    # every line takes the direction of its first letter
        self.assertTrue(validates(sheet))
        self.assertEqual(page.count('class="ss"'), 7)        # ؟ ends a sentence, and so does . before an Arabic letter
        self.assertIn('<span class="ss" id="story-s4">هل هذا صحيح؟</span>', page)
        app, games = build_app(self.root, lesson, sheet)
        self.assertIn(build_course_app.RTL_APP_CSS, app)
        self.assertIn('"arts":[]', app)                      # no article words, so no article game
        arabic = language.profile("ar")                      # والفاكهة (and the fruit) holds الفاكهة for Hör-Bingo
        self.assertTrue(build_course_app.mentions("يشتريان الخبز والفاكهة.", {"الفاكهة"}, [], arabic))
        self.assertEqual([x["m"] for v in games["v"] for x in v["x"]], [[]] * 6)
        self.assertEqual(len(games["s"]), 11)

    def test_a_japanese_course_without_spaces(self):
        lesson, sheet = write_lesson(self.root, JAPANESE)
        page = sheet.read_text(encoding="utf-8")
        self.assertIn('<html lang="ja">', page)
        self.assertNotIn(pack.RTL_CSS, page)
        self.assertTrue(validates(sheet))
        self.assertEqual(page.count('class="ss"'), 6)        # 。 ends a sentence with no space after it
        self.assertEqual(pack.story_sentences(JAPANESE["story"]["paragraphs"][1]["de"], language.profile("ja")),
                         ["店員は「今日はりんごが安いですよ」と言います。", "値段を見ると、本当に安いです。"])
        app, games = build_app(self.root, lesson, sheet)
        self.assertIn('"spaces":false', app)                 # Satzbau asks the browser for the words
        self.assertEqual(len(games["s"]), 11)
        self.assertEqual([x["m"] for v in games["v"] for x in v["x"]], [[]] * 6)
        japanese = language.profile("ja")                    # a verb also counts by its stem: 飲む, 飲みました
        self.assertTrue(build_course_app.mentions("コーヒーを飲みました。", {"飲む"}, japanese["bingo"]["verb_endings"], japanese))
        self.assertEqual(language.word_count(japanese, "毎週土曜日に市場で野菜を買います。"), 8)

    def test_copying_counts_characters_without_spaces(self):
        japanese = language.profile("ja")
        source = pack.runs(language.words(japanese, "本文：毎週土曜日に市場で野菜を買います。"), language.run_length(japanese, 6))
        self.assertEqual(pack.copied_run("私も毎週土曜日に市場で野菜を買います。", [], source, japanese), "毎週土曜日に市場で野菜を")
        self.assertIsNone(pack.copied_run("週末は市場に行きます。", [], source, japanese))

    @NEEDS_DICTS
    def test_arabic_and_japanese_words_are_spoken_by_their_voice(self):
        voices = {"de": "target", "en": "en-US-AvaNeural"}
        speech.use(language.profile("ar"))
        self.assertEqual(speech.segments("Use «سوف» for the future", "en"), [("en", "Use "), ("de", "سوف"), ("en", " for the future")])
        self.assertIn(("de", "السوق"), speech.make_clip("The word السوق means the market.", "en", voices).parts)
        speech.use(language.profile("ja"))
        self.assertEqual(speech.make_clip("毎週土曜日に市場で野菜を買います。", "de", voices).parts, (("de", "毎週土曜日に市場で野菜を買います。"),))
        self.assertIn(("de", "つもりです"), speech.make_clip("Plans: «つもりです» after the verb.", "marked", voices).parts)


if __name__ == "__main__":
    unittest.main()
