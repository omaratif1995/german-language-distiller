"""Build the sample course from original example content (not taken from any book).

usage: python make_sample.py
Writes the lesson bundles to _work/, renders the two reviewed sheets with study_pack.py,
writes _work/course.json and builds Sample_Studienpaket_v1.html (without audio).
It doubles as a compact example of the data the skill authors for every real lesson.
`build()` makes a sample course in another language too (see ../sample-course-es/make_sample.py).
"""
import copy, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "skills" / "language-distiller" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import study_pack as pack  # noqa: E402

SOURCE = HERE / "source" / "sample-lessons.md"
# What differs between sample courses in different languages (the content aside).
GERMAN = {"language": "de", "book": "Beispielkurs", "level": "A2–B1", "groups": ("Wortschatz der Einheit", "Redemittel der Einheit"),
          "title": "Beispielkurs Deutsch", "subtitle": "2 Einheiten · Wortschatz · Grammatik · Redemittel", "app": "Sample_Studienpaket_v1.html"}


def ex(de, en, *targets):
    return {"de": de, "en": en, "targets": list(targets)}


UNITS = [
    {"id": "E1", "label": "Einheit 1", "page": 0, "title": "Der erste Arbeitstag – Im Büro",
     "vocabulary": [
         ("v1", "der", "Kollege", "noun", "die Kollegin, -nen · Plural: die Kollegen · n-noun: den / dem Kollegen", "colleague",
          ex("Mein Kollege zeigt mir am ersten Tag das ganze Büro.", "My colleague shows me the whole office on the first day.", "Kollege")),
         ("v2", "die", "Besprechung", "noun", "Plural: die Besprechungen · in einer Besprechung sein", "meeting",
          ex("Ich kann gerade nicht telefonieren, ich bin in einer Besprechung.", "I can't talk right now, I'm in a meeting.", "Besprechung")),
         ("v3", "der", "Termin", "noun", "Plural: die Termine · einen Termin vereinbaren / verschieben", "appointment",
          ex("Können wir den Termin auf Donnerstag verschieben?", "Can we move the appointment to Thursday?", "Termin")),
         ("v4", None, "sich vorstellen", "verb", "stellt sich vor · hat sich vorgestellt · separable", "to introduce oneself",
          ex("Am ersten Tag stelle ich mich allen Kollegen vor.", "On the first day I introduce myself to all my colleagues.", "stelle", "vor")),
         ("v5", None, "erledigen", "verb", "erledigt · hat erledigt · eine Aufgabe erledigen", "to get done, take care of",
          ex("Keine Sorge, das erledige ich gleich nach der Mittagspause.", "Don't worry, I'll take care of that right after lunch.", "erledige")),
         ("v6", None, "pünktlich", "adjective", "↔ unpünktlich · die Pünktlichkeit", "on time, punctual",
          ex("Bitte sei morgen pünktlich, wir haben um acht eine Besprechung.", "Please be on time tomorrow, we have a meeting at eight.", "pünktlich"))],
     "grammar": {"id": "g1", "title": "Separable verbs – the prefix goes to the end",
                 "meaning": "Many verbs have a prefix that separates from the verb in a main clause.",
                 "rule": "In a main clause the conjugated verb stands in position 2 and the prefix goes to the end. In the Perfekt, -ge- stands between prefix and verb. With a modal verb the infinitive stays together at the end.",
                 "patterns": [("present", "an|fangen → Die Besprechung fängt um neun an."), ("Perfekt", "an|fangen → hat angefangen"),
                              ("modal verb", "Ich muss heute früh anfangen.")],
                 "contrast": "Inseparable prefixes (be-, ver-, er-, ent-) never separate: Ich verstehe die Aufgabe.",
                 "examples": [ex("Die Besprechung fängt um neun Uhr an.", "The meeting starts at nine o'clock.", "fängt", "an"),
                              ex("Ich rufe dich nach der Arbeit an.", "I'll call you after work.", "rufe", "an"),
                              ex("Wir haben das Projekt gestern abgeschlossen.", "We finished the project yesterday.", "abgeschlossen")]},
     "redemittel": [
         ("e1", "Darf ich mich kurz vorstellen? Ich bin … und arbeite als …", "May I briefly introduce myself? I'm … and I work as …",
          "Introduce yourself at a new workplace.", "polite",
          ex("Darf ich mich kurz vorstellen? Ich bin Sara und arbeite als Grafikerin.", "May I briefly introduce myself? I'm Sara and I work as a graphic designer.", "Darf ich mich kurz vorstellen")),
         ("e2", "Könnten Sie mir bitte zeigen, wie …?", "Could you please show me how …?", "Ask a colleague for help.", "polite",
          ex("Könnten Sie mir bitte zeigen, wie der Drucker funktioniert?", "Could you please show me how the printer works?", "Könnten Sie mir bitte zeigen, wie")),
         ("e3", "Bis wann soll ich … erledigen?", "By when should I get … done?", "Ask about a deadline.", None,
          ex("Bis wann soll ich den Bericht erledigen?", "By when should I get the report done?", "Bis wann soll ich", "erledigen"))],
     "story": {"title": "Der Drucker hasst mich", "paragraphs": [
         {"de": "Mein erster Arbeitstag beginnt mit einem Problem: Der Wecker klingelt nicht. Ich ziehe mich in fünf Minuten an "
                "und renne zur S-Bahn. Um Viertel vor neun stehe ich vor dem Büro, außer Atem, aber pünktlich.",
          "en": "My first day at work starts with a problem: the alarm doesn't go off. I get dressed in five minutes and run to the "
                "train. At a quarter to nine I'm standing outside the office, out of breath, but on time.",
          "uses": [{"card": "g1", "form": "ziehe mich in fünf Minuten an"}, {"card": "v6", "form": "pünktlich"}]},
         {"de": "Ein Kollege mit einer riesigen Tasse Kaffee kommt auf mich zu. „Darf ich mich kurz vorstellen? Ich bin Jonas und "
                "arbeite als Techniker.“ Er zeigt mir meinen Platz und erklärt: „Die Besprechung fängt um neun an. Danach hast du "
                "deinen ersten Termin mit der Chefin.“",
          "en": "A colleague with a huge cup of coffee comes up to me. 'May I briefly introduce myself? I'm Jonas and I work as a "
                "technician.' He shows me my desk and explains: 'The meeting starts at nine. After that you have your first "
                "appointment with the boss.'",
          "uses": [{"card": "v1", "form": "Kollege"}, {"card": "e1", "form": "Darf ich mich kurz vorstellen"},
                   {"card": "v2", "form": "Besprechung"}, {"card": "g1", "form": "fängt um neun an"}, {"card": "v3", "form": "Termin"}]},
         {"de": "In der Besprechung stelle ich mich allen kurz vor. Alle sind nett, nur der Drucker nicht: Er blinkt rot und druckt "
                "nichts. Ich frage Jonas: „Könnten Sie mir bitte zeigen, wie der Drucker funktioniert?“ Er lacht. „Sag ruhig du. "
                "Und der Drucker funktioniert nie.“",
          "en": "In the meeting I briefly introduce myself to everyone. Everyone is nice, except the printer: it blinks red and "
                "prints nothing. I ask Jonas: 'Could you please show me how the printer works?' He laughs. 'You can say du. "
                "And the printer never works.'",
          "uses": [{"card": "v4", "form": "stelle ich mich allen kurz vor"}, {"card": "e2", "form": "Könnten Sie mir bitte zeigen, wie"}]},
         {"de": "Am Nachmittag erledige ich zuerst meine E-Mails. Dann bekomme ich meine erste Aufgabe: eine Präsentation für die "
                "Kunden. „Bis wann soll ich die Präsentation fertig machen?“, frage ich. „Bis Donnerstag“, sagt die Chefin. Um sechs "
                "schalte ich den Computer aus und lächle. Morgen stelle ich den Wecker zweimal.",
          "en": "In the afternoon I first deal with my e-mails. Then I get my first task: a presentation for the clients. 'By when "
                "should I finish the presentation?' I ask. 'By Thursday,' says the boss. At six I switch off the computer and "
                "smile. Tomorrow I'll set the alarm twice.",
          "uses": [{"card": "v5", "form": "erledige"}, {"card": "e3", "form": "Bis wann soll ich"},
                   {"card": "g1", "form": "schalte ich den Computer aus"}]}]}},
    {"id": "E2", "label": "Einheit 2", "page": 1, "title": "Pläne fürs Wochenende – Freizeit",
     "vocabulary": [
         ("v1", "der", "Ausflug", "noun", "Plural: die Ausflüge · einen Ausflug machen", "trip, outing",
          ex("Am Samstag machen wir einen Ausflug an den See.", "On Saturday we're going on a trip to the lake.", "Ausflug")),
         ("v2", "die", "Verabredung", "noun", "Plural: die Verabredungen · sich verabreden", "arrangement to meet, date",
          ex("Tut mir leid, heute Abend habe ich schon eine Verabredung.", "Sorry, I already have plans to meet someone tonight.", "Verabredung")),
         ("v3", None, "vorschlagen", "verb", "schlägt vor · hat vorgeschlagen (!) · separable", "to suggest",
          ex("Ich schlage vor, dass wir zusammen kochen.", "I suggest that we cook together.", "schlage", "vor")),
         ("v4", None, "spontan", "adjective", "sich spontan entscheiden", "spontaneous(ly)",
          ex("Wir haben uns ganz spontan für das Kino entschieden.", "We decided on the cinema quite spontaneously.", "spontan")),
         ("v5", "das", "Wetter", "noun", "no plural · bei schönem Wetter", "weather",
          ex("Bei schönem Wetter fahren wir mit dem Rad.", "If the weather is nice, we'll go by bike.", "Wetter"))],
     "grammar": {"id": "g1", "title": "Polite suggestions with könnte and wäre",
                 "meaning": "Konjunktiv II makes a suggestion sound open and friendly.",
                 "rule": "Use könnten + infinitive at the end, or Wie wäre es mit + Dativ. Wir könnten … is softer than Wir müssen …",
                 "patterns": [("könnte", "Wir könnten am Sonntag wandern gehen."), ("wäre", "Wie wäre es mit einem Picknick?"),
                              ("Lust haben", "Hättest du Lust, … zu …?")],
                 "contrast": "Wir können … states that something is possible. Wir könnten … makes a suggestion.",
                 "examples": [ex("Wir könnten am Sonntag wandern gehen.", "We could go hiking on Sunday.", "könnten"),
                              ex("Wie wäre es mit einem Picknick im Park?", "How about a picnic in the park?", "Wie wäre es mit"),
                              ex("Hättest du Lust, mit ins Kino zu kommen?", "Would you like to come to the cinema?", "Hättest du Lust")]},
     "redemittel": [
         ("e1", "Hast du Lust, … zu …?", "Do you feel like …ing?", "Invite a friend informally.", "informal",
          ex("Hast du Lust, am Samstag mit uns zu grillen?", "Do you feel like having a barbecue with us on Saturday?", "Hast du Lust", "zu")),
         ("e2", "Wie wäre es mit …?", "How about …?", "Make a suggestion.", None,
          ex("Wie wäre es mit einem Ausflug an den See?", "How about a trip to the lake?", "Wie wäre es mit")),
         ("e3", "Das passt mir gut. / Das passt mir leider nicht.", "That suits me. / Unfortunately that doesn't suit me.",
          "Accept or decline a suggested time.", None,
          ex("Samstag passt mir gut, aber Sonntag passt mir leider nicht.", "Saturday suits me, but Sunday unfortunately doesn't.", "passt mir gut", "passt mir leider nicht"))],
     "story": {"title": "Der perfekte Samstag", "paragraphs": [
         {"de": "Am Freitagabend schreibt mir Lena: „Hast du Lust, am Samstag mit uns zu grillen?“ Ich schaue sofort in die "
                "Wetter-App. Das Wetter soll perfekt werden: Sonne, 25 Grad, kein Wind.",
          "en": "On Friday evening Lena texts me: 'Do you feel like having a barbecue with us on Saturday?' I check the weather app "
                "straight away. The weather is supposed to be perfect: sun, 25 degrees, no wind.",
          "uses": [{"card": "e1", "form": "Hast du Lust"}, {"card": "v5", "form": "Wetter"}]},
         {"de": "Ich antworte: „Samstag passt mir gut! Aber wie wäre es mit einem Ausflug an den See? Wir könnten dort grillen "
                "und schwimmen.“ Lena findet die Idee toll, nur Tom ist skeptisch.",
          "en": "I reply: 'Saturday suits me! But how about a trip to the lake? We could have a barbecue there and go swimming.' "
                "Lena loves the idea, only Tom is sceptical.",
          "uses": [{"card": "e3", "form": "passt mir gut"}, {"card": "e2", "form": "wie wäre es mit"},
                   {"card": "v1", "form": "Ausflug"}, {"card": "g1", "form": "Wir könnten dort grillen"}]},
         {"de": "Tom schlägt vor, dass wir lieber ins Kino gehen. „Bei dem Wetter? Hättest du nicht Lust, mal etwas Neues zu "
                "machen?“, frage ich. Er gibt auf.",
          "en": "Tom suggests that we'd rather go to the cinema. 'In this weather? Wouldn't you like to do something new for "
                "once?' I ask. He gives in.",
          "uses": [{"card": "v3", "form": "schlägt vor"}, {"card": "g1", "form": "Hättest du nicht Lust"}]},
         {"de": "Am Samstag regnet es. Natürlich. Wir sitzen zu dritt in Lenas Küche, essen Würstchen aus der Pfanne und lachen "
                "viel. Ganz spontan sagt Tom: „Und morgen gehen wir ins Kino?“ Diesmal sage ich ja. Unsere nächste Verabredung steht.",
          "en": "On Saturday it rains. Of course. The three of us sit in Lena's kitchen, eat sausages from the pan and laugh a lot. "
                "Quite spontaneously Tom says: 'And tomorrow we go to the cinema?' This time I say yes. Our next date is set.",
          "uses": [{"card": "v4", "form": "spontan"}, {"card": "v2", "form": "Verabredung"}]}]}},
]

# Spoken grammar explanations for the audio: conversational English, every German word marked «…».
# Spoken grammar explanations: "de" in simple German, the one the app plays; "en" an English backup behind the EN
# button, where every German word comes after a colon or a full stop, so one voice can switch at a natural pause.
NARRATION = {
    "E1": {"g1": {
        "de": "Viele Verben haben eine kleine Vorsilbe, die sich im normalen Satz vom Verb trennt. Das Verb steht auf "
              "Position zwei, und die Vorsilbe springt ganz ans Ende: Die Besprechung fängt um neun Uhr an. Im Perfekt "
              "ist es wieder ein Wort: hat angefangen. Und mit einem Modalverb bleibt alles zusammen am Ende: Ich muss "
              "heute früh anfangen. Aber Vorsicht: Manche Vorsilben trennen sich nie, zum Beispiel bei verstehen und "
              "bekommen. Ich verstehe die Aufgabe.",
        "en": "Many German verbs have a little prefix that breaks away in a normal sentence. The verb stays in position "
              "two, and the prefix jumps to the very end. Listen: «Die Besprechung fängt um neun Uhr an.» In the past "
              "tense, it becomes one word again: «hat angefangen.» And with a modal verb, everything stays together at "
              "the end: «Ich muss heute früh anfangen.» Careful: some prefixes never separate, like these: «verstehen, "
              "bekommen.» Listen: «Ich verstehe die Aufgabe.»"}},
    "E2": {"g1": {
        "de": "Ein Vorschlag klingt offen und freundlich mit könnten oder wäre. Hör zu: Wir könnten am Sonntag wandern "
              "gehen. Das klingt viel weicher als wir müssen. Du kannst auch fragen: Wie wäre es mit einem Picknick im "
              "Park? Und für eine Einladung: Hättest du Lust, mit ins Kino zu kommen? Vergleiche: Wir können heißt nur, "
              "dass etwas möglich ist. Wir könnten ist ein echter Vorschlag.",
        "en": "To make a suggestion sound open and friendly, use one of these: «könnten, wäre.» Listen: «Wir könnten am "
              "Sonntag wandern gehen.» That sounds much softer than: «wir müssen.» You can also ask: «Wie wäre es mit "
              "einem Picknick im Park?» And to invite someone: «Hättest du Lust, mit ins Kino zu kommen?» Compare. This "
              "only says that something is possible: «wir können.» And this is a real suggestion: «wir könnten.»"}},
}

SOURCE_TEXT = """# Sample lessons (original content written for this repository)

## Einheit 1 – Der erste Arbeitstag
Sara beginnt heute in einem neuen Büro. Ihr Kollege Jonas zeigt ihr alles. „Darf ich mich kurz vorstellen?“
Die Besprechung fängt um neun Uhr an. Sara fragt: „Könnten Sie mir bitte zeigen, wie der Drucker funktioniert?“
Wortschatz: der Kollege, die Besprechung, der Termin, sich vorstellen, erledigen, pünktlich.
Grammatik: trennbare Verben (an|fangen, an|rufen, ab|schließen).

## Einheit 2 – Pläne fürs Wochenende
Lena und Tom planen das Wochenende. „Hast du Lust, am Samstag zu grillen?“ – „Wie wäre es mit einem Ausflug?“
Wortschatz: der Ausflug, die Verabredung, vorschlagen, spontan, das Wetter.
Grammatik: Vorschläge mit Konjunktiv II (könnten, wäre, hättest).
"""


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def bundle(unit, here=HERE, source=SOURCE, course=GERMAN):
    work = here / "_work" / unit["id"]
    region = f"p{unit['page']}-lesson"
    src = [{"pdf_index": unit["page"], "region": region, "evidence": unit["title"]}]
    items, vocabulary, redemittel = [], [], []
    for vid, art, lemma, pos, forms, gloss, example in unit["vocabulary"]:
        rec = {"id": vid, "group": course["groups"][0], "lemma": lemma, "pos": pos}
        if art:
            rec["article"] = art
        rec.update(forms=forms, gloss=gloss, examples=[example])
        vocabulary.append(rec)
        items.append({"id": f"i-{vid}", "kind": "vocabulary", "label": f"{art} {lemma}" if art else lemma, "importance": "essential",
                      "sources": copy.deepcopy(src), "decision": "standalone", "home": vid, "reason": "Lesson word list."})
    g = unit["grammar"]
    grammar = [{"id": g["id"], "title": g["title"], "meaning": g["meaning"], "rule": g["rule"],
                "patterns": [{"label": l, "form": f} for l, f in g["patterns"]], "contrast": g["contrast"], "examples": g["examples"]}]
    items.append({"id": "i-g1", "kind": "grammar", "label": g["title"], "importance": "essential", "sources": copy.deepcopy(src),
                  "decision": "standalone", "home": "g1", "reason": "Explicit grammar of the unit."})
    for eid, frame, gloss, when, register, example in unit["redemittel"]:
        rec = {"id": eid, "group": course["groups"][1], "frame": frame, "gloss": gloss, "when": when}
        if register:
            rec["register"] = register
        rec["examples"] = [example]
        redemittel.append(rec)
        items.append({"id": f"i-{eid}", "kind": "expression", "label": frame, "importance": "essential", "sources": copy.deepcopy(src),
                      "decision": "standalone", "home": eid, "reason": "Reusable phrase from the dialogue."})
    items.append({"id": "i-names", "kind": "source_only", "label": "character names", "importance": "incidental",
                  "sources": copy.deepcopy(src), "decision": "exclude", "reason": "Story identity, no learning value."})
    inventory = {"schema_version": 2, "lesson_id": unit["id"], "book": course["book"], "source_sha256": pack.file_hash(source),
                 "scope_label": f"{unit['label']} of the sample source", "scope_pages": [unit["page"]],
                 "pages": [{"pdf_index": unit["page"], "folio": str(unit["page"] + 1), "regions": [
                     {"id": region, "label": unit["title"], "status": "reviewed", "method": "text", "note": "Original sample text."}]}],
                 "items": items, "dependencies": []}
    paths = {n: work / f"{unit['id']}_{n}_v2.json" for n in ("Inventory", "Lesson", "Review")}
    write(paths["Inventory"], inventory)
    lesson = {"schema_version": 2, "lesson_id": unit["id"], "inventory_sha256": pack.file_hash(paths["Inventory"]),
              "title": unit["title"], "level": course["level"], "target_language": course["language"], "gloss_language": "en",
              "vocabulary": vocabulary, "grammar": grammar, "redemittel": redemittel, "story": unit["story"]}
    write(paths["Lesson"], lesson)
    review = {"schema_version": 2, "lesson_id": unit["id"], "inventory_sha256": pack.file_hash(paths["Inventory"]),
              "lesson_sha256": pack.file_hash(paths["Lesson"]), "reviewer": "sample author", "method": "author-second-pass",
              "checks": dict.fromkeys(sorted(pack.CHECKS | {pack.STORY_CHECK}), "pass"), "findings": [],
              "scope_note": "Original sample content written for this repository; not taken from any book."}
    write(paths["Review"], review)
    return paths


def build(units_data, narration, source_text, here=HERE, source=SOURCE, course=GERMAN):
    """Bundles, reviewed sheets, course.json and the app (without audio) of one sample course."""
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    units = []
    for unit in units_data:
        paths = bundle(unit, here, source, course)
        sheet = here / f"{unit['id']}_Studysheet_v1.html"
        sheet.unlink(missing_ok=True)
        args = ["--inventory", str(paths["Inventory"]), "--lesson", str(paths["Lesson"]), "--review", str(paths["Review"]), "--source", str(source)]
        subprocess.run([sys.executable, str(SCRIPTS / "study_pack.py"), "render", *args, "--output", str(sheet)], check=True)
        units.append({"id": unit["id"], "label": unit["label"], "lesson": f"{unit['id']}/{unit['id']}_Lesson_v2.json",
                      "sheet": f"../{sheet.name}"})
    write(here / "_work" / "narration.json", narration)
    write(here / "_work" / "course.json", {"title": course["title"], "subtitle": course["subtitle"],
                                           "narration": "narration.json", "cache": "audio", "episodes_dir": "../Audio",
                                           "new_per_day": 10, "units": units})
    app = here / course["app"]
    app.unlink(missing_ok=True)
    subprocess.run([sys.executable, str(SCRIPTS / "build_course_app.py"), "--course", str(here / "_work" / "course.json"),
                    "--output", str(app), "--no-audio"], check=True)


def main():
    build(UNITS, NARRATION, SOURCE_TEXT)


if __name__ == "__main__":
    main()
