#!/usr/bin/env python3
import unittest

import embed_audio
import speech


LESSON = {
    "title": "Ein Test",
    "target_language": "de",
    "vocabulary": [{
        "id": "v01", "group": "Dinge", "article": "das", "lemma": "Buch",
        "gloss": "book", "forms": "Plural: die Bücher",
        "examples": [{"de": "Ich lese das Buch.", "en": "I read the book."}],
    }],
    "grammar": [{
        "id": "g01", "title": "Präsens", "meaning": "It describes the present.",
        "rule": "Conjugate the verb.", "patterns": [{"label": "pattern", "form": "Subjekt + Verb"}],
        "examples": [
            {"de": "Ich lese.", "en": "I read."},
            {"de": "Wir lesen.", "en": "We read."},
        ],
    }],
    "redemittel": [{
        "id": "e01", "group": "Reagieren", "frame": "Das gefällt mir!",
        "gloss": "I like that!", "when": "React positively.",
        "variants": [{"form": "Sehr schön!", "usage": "React warmly."}],
        "examples": [{"de": "Das gefällt mir sehr gut!", "en": "I like that very much!"}],
    }],
}

HTML = """<!DOCTYPE html><html lang="de"><head><meta name="study-pack-status" content="reviewed"><style></style></head><body><main class="wrap">
<header class="hero"><h1>Ein Test</h1></header>
<h2>Wortschatz</h2><article class="voc" id="v01"><div class="top"><span class="de"><span class="art-das">das</span> Buch</span><span class="en">book</span></div><p class="forms">Plural: die Bücher</p><div class="ex">Ich lese das Buch. <span class="tr">— I read the book.</span></div></article>
<h2>Grammatik</h2><article class="rule" id="g01"><h3>Präsens</h3><div class="ex">Ich lese.<span class="tr">— I read.</span></div><div class="ex">Wir lesen.<span class="tr">— We read.</span></div></article>
<h2>Redemittel</h2><article class="phrase" id="e01"><div class="head">Das gefällt mir!</div><p class="variant">Sehr schön! — React warmly.</p><div class="ex">Das gefällt mir sehr gut!<span class="tr">— I like that very much!</span></div></article>
</main></body></html>"""


STORY_HTML = ('<h2>4 Geschichte</h2><article class="story" id="story"><h3>Ein Buch</h3><div class="story-p" id="story-p1"><p>'
              '<span class="ss" id="story-s1">Ich lese ein <span class="lw" data-card="v01" title="das Buch: book">Buch</span>.</span> '
              '<span class="ss" id="story-s2">Es ist spannend.</span></p><details class="story-tr"><summary>Übersetzung</summary>'
              '<p lang="en">I read a book. It is exciting.</p></details></div></article>')


class EmbeddedAudioTests(unittest.TestCase):
    @unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")
    def test_plan_and_injection_are_self_contained(self):
        clips, plan = embed_audio.lesson_plan(LESSON, "test-voice")
        self.assertEqual(list(plan["explain"]), ["g01"])
        result = embed_audio.inject_audio(HTML, LESSON, {clip_id: "AAAA" for clip_id in clips}, plan)
        self.assertEqual(result.count("<h2"), 3)
        self.assertEqual(result.count('class="speak-button"'), len(plan["controls"]))
        self.assertEqual(len(plan["controls"]), 8)
        self.assertIn('class="listen-open"', result)
        self.assertIn('id="lp"', result)                    # the listening panel: whole lesson, examples, story
        for control in ('id="now-b"', 'id="now-p"', 'id="now-n"', 'id="lp-go"'):   # ⏮ ⏸ ⏭ in the bar, Weiter in the panel
            self.assertIn(control, result)
        self.assertIn('id="v01-x0"', result)                # examples carry ids, so a session can highlight them
        self.assertEqual(result.count("data:audio/mpeg;base64,"), 1)
        self.assertNotIn("https://", result)
        self.assertNotIn("speechSynthesis", result)

    @unittest.skipUnless(speech.dictionaries_available(), "pip install pyspellchecker")
    def test_story_sentences_get_audio_and_their_own_session(self):
        lesson = dict(LESSON, story={"title": "Ein Buch", "paragraphs": [
            {"de": "Ich lese ein Buch. Es ist spannend.", "en": "I read a book. It is exciting.",
             "uses": [{"card": "v01", "form": "Buch"}]}]})
        clips, plan = embed_audio.lesson_plan(lesson, "test-voice")
        self.assertEqual(len(plan["story"]), 1)
        self.assertEqual(len(plan["story"][0]), 2)
        self.assertIn("story", plan["sections"])
        result = embed_audio.inject_audio(HTML.replace("</main>", STORY_HTML + "</main>"), lesson,
                                          {clip_id: "AAAA" for clip_id in clips}, plan)
        self.assertEqual(result.count('class="story-play"'), 1)
        self.assertEqual(result.count('class="speak-button para-play"'), 1)
        self.assertIn(f'id="story-s2" data-audio="{plan["controls"]["story-s2"]}"', result)
        self.assertIn(f'data-card="v01" data-h="{plan["controls"]["v01-head"]}"', result)
        story_steps = embed_audio.story_order("", plan)
        self.assertEqual([step[2] for step in story_steps], ["story", "story-s1", "story-s2"])
        self.assertEqual(len(embed_audio.examples_order("", lesson, plan)), 4)

    def test_speakable_removes_visual_notation(self):
        self.assertEqual(embed_audio.speakable("Subjekt + werden + … + Partizip II"),
                         "Subjekt, werden, Partizip zwei")

    def test_a_written_explanation_is_read_as_one_text(self):
        text = "Nach «als» steht das Verb am Ende. Hör zu:\n> Als ich klein war, …\n\n! Aber Vorsicht: nur einmal."
        self.assertEqual(embed_audio.explanation_blocks(text), [("p", "Nach «als» steht das Verb am Ende. Hör zu:"),
                                                                ("ex", "Als ich klein war, …"), ("warn", "Aber Vorsicht: nur einmal.")])
        self.assertEqual(embed_audio.explanation_speech(text),
                         "Nach als steht das Verb am Ende. Hör zu: Als ich klein war, … Aber Vorsicht: nur einmal.")
        self.assertIn("«als»", embed_audio.explanation_speech(text, marked=True))   # the English backup keeps its marks
        self.assertEqual(embed_audio.explanation_sentences(text)[0][1], ["Nach «als» steht das Verb am Ende.", "Hör zu:"])

    def test_sentences_find_their_words_in_the_voice(self):
        spoken = [(0.0, "Viele"), (0.4, "Verben"), (0.9, "bekommen"), (1.3, "ung"), (2.2, "Nimm"), (2.5, "den"), (2.7, "Stamm")]
        times = embed_audio.sentence_times(["Viele Verben bekommen -ung.", "Nimm den Stamm."], spoken)
        self.assertEqual(times, [0.0, 2.2])
        self.assertEqual(embed_audio.sentence_times(["Ein Satz."], []), [])


if __name__ == "__main__":
    unittest.main()
