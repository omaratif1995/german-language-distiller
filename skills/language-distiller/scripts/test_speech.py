"""Tests for language-aware speech: German words must always reach the German voice."""
import asyncio
import contextlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import speech

VOICES = {"de": "de-voice", "en": "en-voice"}
NEEDS_DICTS = unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")


def parts(text, kind="en"):
    return [(lang, spoken) for lang, spoken in speech.make_clip(text, kind, VOICES).parts]


def german_words(text, kind="en"):
    return " ".join(spoken for lang, spoken in parts(text, kind) if lang == "de")


class SpeechTests(unittest.TestCase):
    def test_german_text_is_never_split(self):
        self.assertEqual(parts("stabil", "de"), [("de", "stabil")])
        self.assertEqual(parts("Das Tolle daran ist, dass man es waschen kann.", "de"),
                         [("de", "Das Tolle daran ist, dass man es waschen kann.")])

    @NEEDS_DICTS
    def test_german_words_inside_english_explanations(self):
        self.assertEqual(german_words("Don't mix them up: with bevor the clause comes second; with während both run in parallel."),
                         "bevor während")
        self.assertIn("Genitiv", german_words("Give the reason with a noun (Genitiv)."))
        self.assertTrue(german_words("als starts a subordinate clause.").startswith("als"))

    @NEEDS_DICTS
    def test_ambiguous_words_follow_their_clause(self):
        self.assertIn("an, auf, in: Dativ", german_words("With an, auf, in: Dativ for a place."))
        segs = parts("After der/die/das -e in the five basic forms.")
        self.assertEqual(segs[1][0], "de")
        self.assertTrue(segs[2][1].startswith("in the five"))
        self.assertEqual(german_words("Inseparable prefixes (be-, ver-) never separate: Ich verstehe die Aufgabe."),
                         "be-, ver- Ich verstehe die Aufgabe.")

    def test_marked_narration_is_exact(self):
        self.assertEqual(parts("Use «als» for the past and «wenn» for the present.", "marked"),
                         [("en", "Use"), ("de", "als"), ("en", "for the past and"), ("de", "wenn"), ("en", "for the present.")])

    def test_a_pause_follows_the_punctuation_after_a_marked_word(self):
        voices = {"de": "de-voice", "en": "en-voice"}       # «als», the verb: the comma belongs to the join after «als»
        self.assertEqual(speech.make_clip("After «als», the verb goes last: «als ich klein war.»", "marked", voices).pauses,
                         (0.08, 0.2, 0.3))

    def test_a_rate_is_part_of_the_clip(self):
        voices = {"de": "de-voice", "en": "en-voice"}
        normal, slower = (speech.make_clip("Hör gut zu.", "de", voices, rate) for rate in ("", "-10%"))
        self.assertNotEqual(normal.clip_id, slower.clip_id)
        self.assertEqual((normal.rate, slower.rate), ("", "-10%"))
        self.assertEqual(speech.segment_id("de-voice", "Hör gut zu."),       # the cache of normal clips stays valid
                         "s_" + __import__("hashlib").sha256("de-voice\0Hör gut zu.".encode()).hexdigest()[:20])

    def test_a_timed_clip_keeps_its_id(self):
        plain, timed = (speech.make_clip("Hör gut zu.", "de", VOICES, "-15%", flag) for flag in (False, True))
        self.assertEqual(plain.clip_id, timed.clip_id)                       # timings come with it; the audio is the same
        self.assertTrue(timed.timed and not plain.timed)

    def test_word_timings_of_joined_segments(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / f"s{i}.mp3" for i in range(2)]
            for path, words in zip(paths, ([(1_500_000, "Listen")], [(2_000_000, "Als"), (6_000_000, "ich")])):
                path.write_bytes(b"x")
                speech._words_file(path).write_text("\n".join(json.dumps({"type": "WordBoundary", "offset": at, "text": word})
                                                              for at, word in words), encoding="utf-8")
            # each segment: 1.0 s decoded, 0.1 s lead-in, 0.8 s once trimmed; 0.3 s of pause after the first
            length = {None: 24000, speech._LEAD: 21600, speech._TRIM: 19200}
            item = speech.make_clip("Listen: «Als ich.»", "marked", VOICES, timed=True)
            found = speech.clip_words(item, paths, measure=lambda path, ff, f=None: length[f])
        self.assertEqual([word for _, word in found], ["Listen", "Als", "ich"])
        self.assertEqual([round(at, 2) for at, _ in found], [0.05, round(0.8 + item.pauses[0] + 0.1, 2),
                                                             round(0.8 + item.pauses[0] + 0.5, 2)])

    @NEEDS_DICTS
    def test_forms_lines_keep_english_glosses_english(self):
        segs = parts("Plural: die Abschlüsse · abschließen = to complete", "mix-de")
        self.assertEqual(segs[0][0], "de")
        self.assertEqual(segs[-1], ("en", "to complete"))

    @NEEDS_DICTS
    def test_course_book_notation(self):
        self.assertEqual(parts("Plural: die Bohnen · A: die Fisole", "mix-de"),
                         [("de", "Plural: die Bohnen. in Österreich: die Fisole")])
        self.assertIn("in der Schweiz auch: gratis", german_words("= kostenlos · A/CH also: gratis", "mix-de"))
        self.assertIn("die Babysitter", german_words("Plural: die Babysitter · die Babysitterin, -nen", "mix-de"))
        self.assertIn("vom Typ her", german_words("Plural: die Typen · vom Typ her = in terms of personality", "mix-de"))
        self.assertEqual(parts("eine steile Karriere = a rapid rise · also: steep", "mix-de")[-1], ("en", "a rapid rise. also: steep"))
        self.assertEqual(parts("die Gebühr, -en = fee", "mix-de")[-1], ("en", "fee"))
        self.assertEqual(parts("ich schütt(e)le · den Kopf schütteln", "mix-de"), [("de", "ich schüttele. den Kopf schütteln")])
        self.assertEqual(parts("mit etwas rechnen = expect sth", "mix-de")[-1], ("en", "expect something"))

    @NEEDS_DICTS
    def test_acronyms_compounds_and_names_in_english(self):
        self.assertEqual(parts("I've saved the file on my USB stick."), [("en", "I've saved the file on my USB stick.")])
        self.assertEqual(german_words("The S-Bahn is faster than the bus."), "S-Bahn")
        self.assertEqual(german_words("Verb + -ung = noun (die)"), "Verb, ung die")

    @NEEDS_DICTS
    def test_context_names_cognates_and_numbers(self):
        self.assertIn("Konjunktiv zwei", german_words("Konjunktiv II forms: hätte, wäre, würde"))
        self.assertEqual(parts("Kind regards, Sara Weber")[0], ("en", "Kind regards, Sara"))
        self.assertEqual(german_words("If I had more time, I would travel to Berlin more often."), "")
        self.assertEqual(parts("regional = from the area · saisonal = in season", "mix-de"),
                         [("de", "regional"), ("en", "from the area."), ("de", "saisonal"), ("en", "in season")])
        self.assertEqual(german_words("Food words stay singular with amounts: 300 g Mehl"), "300 g Mehl")
        self.assertEqual(german_words("Comparison forms: umlaut, irregular, am …sten"), "am, sten")
        self.assertEqual(german_words("I can't imagine …ing at all"), "")
        self.assertTrue(german_words("frisst auf · animals fressen, people essen", "mix-de").endswith("essen"))
        self.assertEqual(german_words("hungrig (sein) = Hunger haben", "mix-de"), "hungrig, sein, Hunger haben")

    def test_marked_german_parts_keep_their_spacing(self):
        self.assertEqual(parts("«Ich gehe.» «Du bleibst.» Then English.", "marked"),
                         [("de", "Ich gehe. Du bleibst."), ("en", "Then English.")])

    @NEEDS_DICTS
    def test_lint_finds_unmarked_german_in_narration(self):
        self.assertEqual(speech.unmarked_german("Use «als» with the Genitiv, and I mean it."), ["Genitiv"])
        self.assertEqual(speech.unmarked_german("Use «als» with the «Genitiv»."), [])

    def test_clip_ids_depend_on_voices_and_text(self):
        a = speech.make_clip("Hallo", "de", VOICES).clip_id
        self.assertEqual(a, speech.make_clip("Hallo", "de", VOICES).clip_id)
        self.assertNotEqual(a, speech.make_clip("Hallo", "de", {"de": "other", "en": "en-voice"}).clip_id)

    def test_speakable_notation(self):
        self.assertEqual(speech.speakable("Subjekt + werden + … + Partizip II", "de"), "Subjekt, werden, Partizip zwei")
        self.assertEqual(speech.speakable("aussehen → das Aussehen", "de"), "aussehen wird zu das Aussehen")
        self.assertEqual(speech.speakable("flat / thin", "en"), "flat or thin")


class FakeVoice:
    """edge_tts.Communicate without the network. The requests numbered in `hang` never get an answer, like one sent
    just before the computer slept; the others return a little audio. Each writes some audio first, as edge-tts does."""
    hang, requests = set(), 0

    def __init__(self, text, voice, rate, boundary=None):
        pass

    async def save(self, audio, words=None):
        FakeVoice.requests += 1
        Path(audio).write_bytes(b"\xff\xf3" * 600)
        if FakeVoice.requests in FakeVoice.hang:
            await asyncio.Event().wait()


class VoiceRequestTests(unittest.TestCase):
    @contextlib.contextmanager
    def voice_service(self, hang):
        FakeVoice.hang, FakeVoice.requests = set(hang), 0
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.dict(sys.modules, {"edge_tts": types.SimpleNamespace(Communicate=FakeVoice)}), \
                mock.patch.object(speech, "_time_limit", lambda spoken: 0.05), \
                mock.patch.object(speech, "RETRY_SECONDS", 0):
            yield Path(folder)

    def test_a_request_without_an_answer_is_sent_again(self):
        item = speech.make_clip("Hör gut zu.", "de", VOICES)
        with self.voice_service(hang={1}) as cache:
            made = asyncio.run(speech.synthesize({item.clip_id: item}, cache, VOICES))
            self.assertGreater(made[item.clip_id].stat().st_size, 256)
            self.assertEqual(FakeVoice.requests, 2)
            self.assertEqual([p.name for p in (cache / "segments").iterdir() if ".part" in p.name], [])

    def test_a_voice_service_that_never_answers_ends_with_a_reason(self):
        item = speech.make_clip("Hör gut zu.", "de", VOICES)
        with self.voice_service(hang=range(1, 10)) as cache:
            with self.assertRaisesRegex(speech.SpeechError, r"'Hör gut zu\.' \(4 tries of at most 0 s\): TimeoutError$"):
                asyncio.run(speech.synthesize({item.clip_id: item}, cache, VOICES))
            self.assertEqual(FakeVoice.requests, 4)
            self.assertEqual(list((cache / "clips").iterdir()), [])

    def test_the_time_limit_leaves_long_texts_time(self):
        self.assertEqual(speech._time_limit("x" * 20), 64)
        self.assertGreater(speech._time_limit("x" * 650), 2 * 60)     # 650 characters: about a minute of German speech


if __name__ == "__main__":
    unittest.main()
