"""Build the Spanish sample course from original example content (not taken from any book).

usage: python make_sample.py
The same pipeline as the German sample (../sample-course/make_sample.py) with the Spanish language profile:
two reviewed sheets (Vocabulario, Gramática, Expresiones útiles, Historia), _work/course.json and
Curso_de_ejemplo_v1.html (without audio; the app speaks English to the learner, the content is Spanish).
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("sample", HERE.parent / "sample-course" / "make_sample.py")
sample = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sample)
ex = sample.ex

SPANISH = {"language": "es", "book": "Curso de ejemplo", "level": "A2", "groups": ("Vocabulario de la unidad", "Expresiones de la unidad"),
           "title": "Curso de español", "subtitle": "2 unidades · Vocabulario · Gramática · Expresiones útiles",
           "app": "Curso_de_ejemplo_v1.html"}

UNITS = [
    {"id": "S1", "label": "Unidad 1", "page": 0, "title": "En el mercado – Comprar comida fresca",
     "vocabulary": [
         ("v1", "el", "puesto", "noun", "Plural: los puestos · el puesto de fruta", "(market) stall",
          ex("En el puesto de la esquina venden las mejores naranjas del barrio.",
             "The stall on the corner sells the best oranges in the neighbourhood.", "puesto")),
         ("v2", "la", "cesta", "noun", "Plural: las cestas", "basket",
          ex("Siempre llevo mi propia cesta para no usar bolsas de plástico.",
             "I always take my own basket so that I don't use plastic bags.", "cesta")),
         ("v3", None, "regatear", "verb", "regateo · he regateado", "to haggle",
          ex("En este mercado nadie regatea: los precios están en carteles.",
             "Nobody haggles at this market: the prices are on signs.", "regatea")),
         ("v4", None, "fresco", "adjective", "fresca · frescos · frescas", "fresh",
          ex("El pescado está tan fresco que todavía huele a mar.", "The fish is so fresh that it still smells of the sea.", "fresco")),
         ("v5", "la", "oferta", "noun", "Plural: las ofertas · estar de oferta", "special offer",
          ex("Las fresas están de oferta: dos kilos por cinco euros.", "Strawberries are on special offer: two kilos for five euros.", "oferta")),
         ("v6", None, "probar", "verb", "pruebo · he probado (o → ue)", "to try, to taste",
          ex("¿Puedo probar un trozo de este queso antes de comprarlo?", "Can I try a piece of this cheese before I buy it?", "probar"))],
     "grammar": {"id": "g1", "title": "Direct object pronouns: lo, la, los, las",
                 "meaning": "They replace a thing or person you have already mentioned, so you don't repeat the noun.",
                 "rule": "The pronoun goes right before the conjugated verb. With an infinitive it can also be attached to its end. "
                         "It takes the gender and number of the noun it replaces.",
                 "patterns": [("before the verb", "Los compro."), ("with an infinitive", "Voy a probarlo. = Lo voy a probar."),
                              ("feminine plural", "Las llevo en la cesta.")],
                 "contrast": "le and les are for the person who receives something (indirect object): Le doy el dinero.",
                 "examples": [ex("Estos tomates están muy baratos; los compro todos.", "These tomatoes are very cheap; I'll buy them all.",
                                 "los compro"),
                              ex("¿El queso de cabra? Lo voy a probar ahora mismo.", "The goat's cheese? I'm going to try it right now.",
                                 "Lo voy a probar"),
                              ex("Las naranjas, las llevo yo en la cesta.", "I'll carry the oranges in the basket.", "las llevo")]},
     "redemittel": [
         ("e1", "¿Cuánto cuesta …?", "How much is …?", "Ask the price of something.", None,
          ex("¿Cuánto cuesta un kilo de tomates?", "How much is a kilo of tomatoes?", "Cuánto cuesta")),
         ("e2", "Me pone …, por favor.", "I'll have …, please.", "Order at a market stall or in a bar.", "Spain, everyday",
          ex("Me pone medio kilo de fresas, por favor.", "I'll have half a kilo of strawberries, please.", "Me pone", "por favor")),
         ("e3", "¿Algo más? – No, nada más, gracias.", "Anything else? – No, nothing else, thanks.", "Answer the seller at the end.", None,
          ex("¿Algo más? – No, nada más, gracias. ¿Cuánto es todo?", "Anything else? – No, nothing else, thanks. How much is it altogether?",
             "No, nada más, gracias"))],
     "story": {"title": "Un sábado en el mercado", "paragraphs": [
         {"de": "El sábado por la mañana, Marta va al mercado con su cesta. En el primer puesto, las fresas están de oferta y huelen "
                "de maravilla.",
          "en": "On Saturday morning Marta goes to the market with her basket. At the first stall the strawberries are on special "
                "offer and smell wonderful.",
          "uses": [{"card": "v2", "form": "cesta"}, {"card": "v1", "form": "puesto"}, {"card": "v5", "form": "oferta"}]},
         {"de": "—Me pone un kilo de fresas, por favor —dice Marta. —Están muy frescas, ¡pruébelas! —contesta el vendedor. Marta "
                "prueba una y las compra sin pensarlo.",
          "en": "'I'll have a kilo of strawberries, please,' says Marta. 'They're very fresh, try them!' answers the seller. Marta "
                "tries one and buys them without a second thought.",
          "uses": [{"card": "e2", "form": "Me pone"}, {"card": "v4", "form": "frescas"}, {"card": "v6", "form": "prueba"},
                   {"card": "g1", "form": "las compra"}]},
         {"de": "—¿Cuánto cuesta este queso de cabra? —pregunta Marta en el puesto de quesos. Es caro, y el vendedor no quiere "
                "regatear. —Bueno, lo voy a llevar igualmente —dice ella.",
          "en": "'How much is this goat's cheese?' Marta asks at the cheese stall. It is expensive, and the seller doesn't want to "
                "haggle. 'Well, I'll take it anyway,' she says.",
          "uses": [{"card": "e1", "form": "Cuánto cuesta"}, {"card": "v3", "form": "regatear"}, {"card": "g1", "form": "lo voy a llevar"}]},
         {"de": "—¿Algo más? —pregunta el vendedor. —No, nada más, gracias —responde ella. En casa, Marta abre la cesta y sonríe: "
                "fresas, queso y el mejor plan para el domingo.",
          "en": "'Anything else?' asks the seller. 'No, nothing else, thanks,' she answers. At home Marta opens the basket and "
                "smiles: strawberries, cheese and the best plan for Sunday.",
          "uses": [{"card": "e3", "form": "No, nada más, gracias"}]}]}},
    {"id": "S2", "label": "Unidad 2", "page": 1, "title": "Un piso nuevo – Buscar casa",
     "vocabulary": [
         ("v1", "el", "alquiler", "noun", "Plural: los alquileres · pagar el alquiler", "rent",
          ex("El alquiler incluye la luz y el agua, pero no internet.", "The rent includes electricity and water, but not the internet.",
             "alquiler")),
         ("v2", "la", "fianza", "noun", "Plural: las fianzas", "deposit",
          ex("Al firmar el contrato, pagamos dos meses de fianza.", "When we signed the contract, we paid two months' deposit.", "fianza")),
         ("v3", None, "compartir", "verb", "comparto · he compartido", "to share",
          ex("Comparto el piso con dos estudiantes de Valencia.", "I share the flat with two students from Valencia.", "Comparto")),
         ("v4", None, "luminoso", "adjective", "luminosa · luminosos · luminosas", "bright, full of light",
          ex("El salón es pequeño, pero muy luminoso.", "The living room is small but very bright.", "luminoso")),
         ("v5", "la", "mudanza", "noun", "Plural: las mudanzas · hacer la mudanza", "move (to a new home)",
          ex("La mudanza fue un caos: tres días de cajas y escaleras.", "The move was chaos: three days of boxes and stairs.", "mudanza")),
         ("v6", "el", "vecino", "noun", "la vecina · Plural: los vecinos", "neighbour",
          ex("Nuestro vecino del tercero toca el piano todas las noches.", "Our neighbour on the third floor plays the piano every night.",
             "vecino"))],
     "grammar": {"id": "g1", "title": "Comparisons: más … que, tan … como",
                 "meaning": "Compare two things: one has more or less of a quality, or both have it equally.",
                 "rule": "más / menos + adjective + que; tan + adjective + como. The adjective agrees with its noun. bueno and malo "
                         "have short forms: mejor, peor.",
                 "patterns": [("more", "más caro que"), ("equal", "tan grande como"), ("better", "mejor que, not más bueno que")],
                 "contrast": "tanto / tanta + noun + como compares amounts: tanto ruido como antes.",
                 "examples": [ex("Este piso es más luminoso que el anterior.", "This flat is brighter than the previous one.", "más luminoso que"),
                              ex("Aquí el alquiler es tan caro como en el centro.", "Here the rent is as expensive as in the centre.",
                                 "tan caro como"),
                              ex("Mi calle nueva es mucho más tranquila que la antigua.", "My new street is much quieter than the old one.",
                                 "más tranquila que")]},
     "redemittel": [
         ("e1", "Me interesa el piso de …", "I'm interested in the flat on …", "Answer a flat advert by phone or e-mail.", None,
          ex("Buenos días, me interesa el piso de la calle Mayor. ¿Sigue libre?",
             "Good morning, I'm interested in the flat on Calle Mayor. Is it still available?", "me interesa el piso de")),
         ("e2", "¿Se puede visitar …?", "Can I come and see …?", "Ask to view the flat.", None,
          ex("¿Se puede visitar el piso este jueves por la tarde?", "Can I see the flat this Thursday afternoon?", "Se puede visitar")),
         ("e3", "¿Están incluidos los gastos?", "Are the bills included?", "Ask what the rent covers.", None,
          ex("Perdone, ¿están incluidos los gastos de agua y luz?", "Excuse me, are the water and electricity bills included?",
             "están incluidos los gastos"))],
     "story": {"title": "Un piso con mucha luz", "paragraphs": [
         {"de": "Después de un mes buscando, Álvaro encuentra un anuncio: «Piso luminoso cerca del metro». Llama enseguida: "
                "—Buenos días, me interesa el piso de la calle Olmo. ¿Se puede visitar mañana?",
          "en": "After a month of searching, Álvaro finds an advert: 'Bright flat near the metro'. He calls straight away: 'Good "
                "morning, I'm interested in the flat on Calle Olmo. Can I come and see it tomorrow?'",
          "uses": [{"card": "v4", "form": "luminoso"}, {"card": "e1", "form": "me interesa el piso de"},
                   {"card": "e2", "form": "Se puede visitar"}]},
         {"de": "El piso es pequeño, pero más luminoso que todos los que ha visto. El alquiler es tan caro como en el centro, así "
                "que Álvaro pregunta: —¿Están incluidos los gastos?",
          "en": "The flat is small, but brighter than all the ones he has seen. The rent is as expensive as in the centre, so "
                "Álvaro asks: 'Are the bills included?'",
          "uses": [{"card": "g1", "form": "más luminoso que"}, {"card": "v1", "form": "alquiler"}, {"card": "g1", "form": "tan caro como"},
                   {"card": "e3", "form": "Están incluidos los gastos"}]},
         {"de": "La dueña dice que sí y le pide dos meses de fianza. Álvaro firma, llama a su amiga Nuria y le pregunta si quiere "
                "compartir el piso con él.",
          "en": "The landlady says yes and asks him for two months' deposit. Álvaro signs, calls his friend Nuria and asks her "
                "whether she wants to share the flat with him.",
          "uses": [{"card": "v2", "form": "fianza"}, {"card": "v3", "form": "compartir"}]},
         {"de": "La mudanza es un domingo de lluvia. Entre cajas y risas aparece el vecino del cuarto con una tortilla: "
                "—¡Bienvenidos al edificio! —dice con una sonrisa. Esa noche cenan en el suelo del salón, más felices que nunca.",
          "en": "The move is on a rainy Sunday. Between boxes and laughter, the neighbour from the fourth floor turns up with a "
                "tortilla. 'Welcome to the building!' he says with a smile. That night they have dinner on the living-room floor, "
                "happier than ever.",
          "uses": [{"card": "v5", "form": "mudanza"}, {"card": "v6", "form": "vecino"}]}]}},
]
# Spoken grammar explanations: "de" in simple Spanish (the target language), the one the app plays; "en" an English
# backup behind the EN button, where every Spanish word comes after a colon or a full stop.
NARRATION = {
    "S1": {"g1": {
        "de": "Cuando ya sabes de qué hablas, no repites la palabra. La cambias por una palabra corta: lo, la, los o las. Va "
              "justo antes del verbo: Los compro. Con un infinitivo, también puedes ponerla al final: Voy a probarlo. Significa "
              "lo mismo que: Lo voy a probar. Pero cuidado: le y les son para la persona que recibe algo, no para la cosa.",
        "en": "When it's clear what you're talking about, Spanish replaces the thing with a short word: «lo, la, los, las.» It "
              "goes right before the verb. Listen: «Los compro.» With an infinitive, you can also hang it on the end: «Voy a "
              "probarlo.» That means the same as: «Lo voy a probar.» Careful. For the person who receives something, Spanish "
              "uses other words: «le, les.»"}},
    "S2": {"g1": {
        "de": "Para comparar dos cosas, usas más o menos con que: Este piso es más luminoso que el anterior. Cuando las dos "
              "cosas son iguales, usas tan con como: El alquiler es tan caro como en el centro. Y recuerda las formas cortas: "
              "no se dice más bueno, sino mejor.",
        "en": "To compare two things, use these words: «más, menos, que.» Listen: «Este piso es más luminoso que el anterior.» "
              "When both are the same, use these: «tan, como.» Listen: «El alquiler es tan caro como en el centro.» And remember "
              "the short form for better: «mejor.»"}},
}
SOURCE_TEXT = """# Lecciones de ejemplo (contenido original escrito para este repositorio)
## Unidad 1 – En el mercado
Marta hace la compra en el mercado del barrio y habla con los vendedores.
Vocabulario: el puesto, la cesta, regatear, fresco, la oferta, probar.
Gramática: pronombres de objeto directo (lo, la, los, las).
Expresiones: ¿Cuánto cuesta …? · Me pone …, por favor. · ¿Algo más?
## Unidad 2 – Un piso nuevo
Álvaro busca un piso y llama por un anuncio.
Vocabulario: el alquiler, la fianza, compartir, luminoso, la mudanza, el vecino.
Gramática: comparaciones (más … que, tan … como).
Expresiones: Me interesa el piso de … · ¿Se puede visitar …? · ¿Están incluidos los gastos?
"""


if __name__ == "__main__":
    sample.build(UNITS, NARRATION, SOURCE_TEXT, here=HERE, source=HERE / "source" / "lecciones.md", course=SPANISH)
