"""Free-text answers (slots 21-24), generated so they actually carry signal.

The previous generator wrote the literal string "feedback scris" with probability 0.2.
That parses, but it is useless: the four open questions are the only place a reader (or a
sentiment classifier) can learn anything the Likert items don't already say.

Design notes, because they are easy to get wrong:

* Sentiment TRACKS THE SCORES. The tier is derived from the attempt's own continuous
  item values, so a student who rated the course 4.6 writes praise and one who rated it
  2.1 complains. Text and numbers are two views of the same latent opinion.

* ~10% of the time we deliberately draw from an ADJACENT tier. Real people leave nitpicks
  in glowing reviews. Without this, a classifier trained on the result scores ~99% and the
  team learns nothing from building it.

* The nouns are SHARED between the positive and negative banks on purpose. If only the
  negative bank ever said "laborator", a naive-Bayes classifier would degenerate into a
  keyword lookup. The discriminating signal lives in the adjectives, verbs and complaint
  clauses -- as it does in real text.

* `difficulty` is not a sentiment question at all. The Moodle wording is "dificultatea
  principală în urmărirea acestei discipline provine din:" -- it asks for a CAUSE. It is
  modelled as a choice among causes, weighted by the student's own worst dimensions, so a
  heavy course really does produce "volum" answers and a course with bad slides really
  does produce "materiale" ones.

* Most students write nothing. The fill rate is U-shaped in sentiment: strong opinions,
  in either direction, are far likelier to be written down than indifference.
"""

from slots import COURSE_ITEMS, ASSIST_ITEMS, PROF_ITEMS

# Shared vocabulary. Deliberately reused across sentiment tiers.
SLOTS_VOCAB = {
    "NOUN_ASP": [
        "cursul", "laboratorul", "materialul de curs", "proiectul", "tematica",
        "partea practica", "exemplele de la curs", "temele", "seminarul", "suportul de curs",
    ],
    "NOUN_ASP_ACC": [
        "cursul", "laboratorul", "proiectul", "tematica", "partea practica", "temele",
    ],
    "ADJ_G": [
        "util", "interesant", "bine structurat", "clar", "aplicat", "coerent",
        "bine organizat", "atractiv",
    ],
    "ADJ_B": [
        "haotic", "confuz", "plictisitor", "prea teoretic", "dezorganizat",
        "superficial", "greoi",
    ],
    "VP_G": [
        "se vede ca materia e stapanita", "exemplele sunt din practica",
        "se poate aplica in proiecte reale", "ritmul e potrivit",
        "laboratoarele completeaza bine cursul", "am inteles la ce foloseste",
    ],
    "VP_PERSON": [
        "explica pe inteles", "e disponibil la intrebari", "da exemple din industrie",
        "corecteaza rapid temele", "raspunde pe forum", "are rabdare cu studentii",
    ],
    "PERSON": [
        "profesorul", "titularul", "asistentul", "cadrul didactic",
    ],
    "COMPLAINT": [
        "slide-urile sunt incomplete", "nu exista exemple rezolvate",
        "ritmul e prea alert", "laboratorul nu are legatura cu cursul",
        "notarea nu e transparenta", "echipamentele din laborator sunt vechi",
        "deadline-urile se suprapun cu alte materii", "nu se raspunde pe forum",
    ],
    "VP_FIX": [
        "actualizate", "restructurate", "corelate cu laboratorul", "publicate din timp",
        "explicate mai pe indelete",
    ],
    "COP": ["e", "este", "mi s-a parut"],
    "NOUN_PREREQ": [
        "analiza matematica", "algebra", "programare", "structuri de date", "fizica",
    ],
    "NOUN_TIME": ["timpul disponibil", "numarul de credite", "restul materiilor"],
}

BANKS = {
    "positive": {
        "strong_pos": [
            "{ADJ_G} {NOUN_ASP}, {VP_G}.",
            "Mi-a placut {NOUN_ASP_ACC} si faptul ca {VP_G}.",
            "{PERSON} {VP_PERSON} si {VP_PERSON}.",
            "Cea mai buna materie din semestru, {VP_G}.",
            "{NOUN_ASP} {COP} chiar {ADJ_G}; {VP_G}.",
            "Foarte {ADJ_G}. {PERSON} {VP_PERSON}.",
            "{VP_G}, iar {NOUN_ASP} {COP} {ADJ_G}.",
            "Recomand materia: {VP_G}.",
        ],
        "pos": [
            "{NOUN_ASP} {COP} {ADJ_G}.",
            "{PERSON} {VP_PERSON}.",
            "In general {ADJ_G}, {VP_G}.",
            "Mi-a placut ca {VP_G}.",
            "{NOUN_ASP} {COP} {ADJ_G} si {VP_G}.",
            "Partea buna e ca {VP_G}.",
        ],
        "neutral": [
            "{NOUN_ASP} {COP} ok.",
            "{NOUN_ASP} {COP} {ADJ_G}, dar {COMPLAINT}.",
            "In general bine, desi {COMPLAINT}.",
            "Nimic deosebit, dar {VP_G}.",
        ],
        "neg": [
            "Doar {NOUN_ASP}, in rest {COMPLAINT}.",
            "Putine. {COMPLAINT}.",
            "Nu prea am ce sa laud; {COMPLAINT}.",
        ],
        "strong_neg": [
            "Niciun aspect pozitiv.",
            "Nimic. {COMPLAINT}.",
            "Greu de gasit ceva; {COMPLAINT}.",
        ],
    },
    "negative": {
        "strong_pos": [
            "Nu am ce sa reprosez.",
            "Nimic major; poate {NOUN_ASP} ar putea fi {VP_FIX}.",
            "Aproape nimic.",
        ],
        "pos": [
            "{NOUN_ASP} ar putea fi {VP_FIX}.",
            "Doar un detaliu: {COMPLAINT}.",
            "Ar ajuta daca {NOUN_ASP} ar fi {VP_FIX}.",
        ],
        "neutral": [
            "{NOUN_ASP} ar trebui {VP_FIX}.",
            "{COMPLAINT}.",
            "{COMPLAINT}. Ar ajuta daca {NOUN_ASP} ar fi {VP_FIX}.",
        ],
        "neg": [
            "Prea {ADJ_B} {NOUN_ASP_ACC}, {COMPLAINT}.",
            "{COMPLAINT}. Ar ajuta daca {NOUN_ASP} ar fi {VP_FIX}.",
            "Nu mi-a placut ca {COMPLAINT}.",
            "{NOUN_ASP} {COP} {ADJ_B}; {COMPLAINT}.",
            "{COMPLAINT} si {COMPLAINT}.",
        ],
        "strong_neg": [
            "Totul: {COMPLAINT}, {COMPLAINT}.",
            "{NOUN_ASP} {COP} extrem de {ADJ_B}. {COMPLAINT}.",
            "Foarte {ADJ_B}. {COMPLAINT} si nimeni nu pare sa observe.",
            "{COMPLAINT}. Materia trebuie regandita din temelie.",
        ],
    },
    "other": {
        "strong_pos": ["Felicitari echipei.", "Continuati asa.", "Multumesc pentru semestru."],
        "pos": ["Ar merge mai multe exemple.", "Poate mai multe laboratoare aplicate."],
        "neutral": ["-", "nimic", "n/a", "Nu am alte comentarii.", "Sala e prea rece."],
        "neg": ["Orarul de la ora 8 e brutal.", "Prea multe teme in aceeasi saptamana."],
        "strong_neg": [
            "Ar trebui schimbat titularul.",
            "Cea mai slaba materie de pana acum.",
            "Sper sa se schimbe ceva anul viitor.",
        ],
    },
}

# `difficulty` -- cause attribution, not sentiment.
DIFFICULTY_BANK = {
    "volum": [
        "volumul mare de teme raportat la {NOUN_TIME}",
        "prea multe teme in paralel cu alte discipline",
        "cantitatea de materie fata de numarul de credite",
    ],
    "curs": [
        "explicatiile de la curs, care sar peste pasi",
        "ritmul alert al cursului",
        "faptul ca notiunile noi nu sunt introduse gradual",
    ],
    "laborator": [
        "faptul ca laboratorul presupune lucruri neexplicate",
        "decalajul dintre curs si laborator",
        "timpul insuficient pentru a termina laboratorul",
    ],
    "materiale": [
        "lipsa unor exemple rezolvate in suportul de curs",
        "slide-urile incomplete",
        "lipsa unei bibliografii clare",
    ],
    "prereq": [
        "lipsa cunostintelor de la {NOUN_PREREQ}",
        "faptul ca se presupun notiuni de {NOUN_PREREQ}",
    ],
    "personal": [
        "organizarea mea a timpului",
        "faptul ca nu am reusit sa tin ritmul",
    ],
    "niciuna": [
        "nu am intampinat dificultati deosebite",
        "nimic anume",
    ],
}

TIERS = ["strong_neg", "neg", "neutral", "pos", "strong_pos"]

# Diacritic-stripping is already baked into the banks above (real Moodle text is mostly
# written without them). This is the reverse: occasionally ADD them back, so the corpus
# is not uniformly ASCII and the team has to normalise.
_DIACRITICS = str.maketrans({"a": "ă", "i": "î", "s": "ș", "t": "ț"})


def _tier(z):
    if z < -1.0:
        return "strong_neg"
    if z < -0.25:
        return "neg"
    if z < 0.25:
        return "neutral"
    if z < 1.0:
        return "pos"
    return "strong_pos"


def _render(rng, template):
    """Fill {SLOT} placeholders. A slot repeated in one template draws distinct values,
    so we never produce 'cursul si cursul'."""
    used = {}
    out, i = [], 0
    while i < len(template):
        ch = template[i]
        if ch == "{":
            j = template.index("}", i)
            slot = template[i + 1 : j]
            pool = [v for v in SLOTS_VOCAB[slot] if v not in used.get(slot, ())]
            if not pool:
                pool = SLOTS_VOCAB[slot]
            value = rng.choice(pool)
            used.setdefault(slot, set()).add(value)
            out.append(value)
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _surface_noise(rng, text):
    if not text:
        return text
    if rng.random() < 0.15:  # a minority of students type with diacritics
        text = text.translate(_DIACRITICS)
    if rng.random() < 0.20:
        text = text.rstrip(".")
    if rng.random() < 0.10:
        text = text[:1].lower() + text[1:]
    return text


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _fill_probability(field, z, part):
    """U-shaped in sentiment: the indifferent middle writes least. Engaged students
    (higher attendance) write a little more."""
    if field == "positive":
        p = 0.16 + 0.10 * z + 0.06 * z * z
    elif field == "negative":
        p = 0.14 - 0.11 * z + 0.07 * z * z
    elif field == "difficulty":
        p = 0.20 + 0.05 * max(0.0, -z)
    else:  # other
        p = 0.07 + 0.04 * z * z
    p *= 1.0 + 0.12 * (part - 4)
    return _clamp(p, 0.03, 0.70)


def _pick_cause(rng, items, workload_z, sentiment_z):
    """Weighted by the student's own worst dimensions, so the stated cause is consistent
    with the numbers they gave."""
    import math

    weights = {
        "volum": math.exp(1.20 * workload_z),
        "curs": math.exp(1.00 * (3.83 - items["prof_teach"])),
        "laborator": math.exp(1.00 * (3.83 - items["assist_teach"])),
        "materiale": math.exp(1.00 * (3.83 - items["lecture_doc"])),
        "prereq": 0.75,
        "personal": 0.85,
        "niciuna": math.exp(1.10 * sentiment_z),
    }
    causes = sorted(weights)
    return rng.choices(causes, weights=[weights[c] for c in causes])[0]


def generate_texts(rng, items, workload_z, part):
    """-> ({slot: text}, truth) for the four free-text slots.

    `truth` is the ground-truth sentiment label, for training/evaluating a classifier
    later. It is returned separately and written to a sidecar -- NEVER into the 25-slot
    response list, which the consumers parse strictly by position.
    """
    scored = [items[k] for k in PROF_ITEMS + ASSIST_ITEMS + COURSE_ITEMS]
    mean = sum(scored) / len(scored)
    z = (mean - 3.83) / 0.62
    tier = _tier(z)

    texts, per_field = {}, {}
    for field in ("positive", "negative", "difficulty", "other"):
        if rng.random() >= _fill_probability(field, z, part):
            texts[field] = ""
            continue

        if field == "difficulty":
            cause = _pick_cause(rng, items, workload_z, z)
            text = _render(rng, rng.choice(DIFFICULTY_BANK[cause]))
            per_field[field] = {"cause": cause}
        else:
            # ~10% label noise: draw from an adjacent tier. Keeps the corpus learnable
            # but not memorisable.
            drawn = tier
            if rng.random() < 0.10:
                idx = _clamp(TIERS.index(tier) + rng.choice((-1, 1)), 0, len(TIERS) - 1)
                drawn = TIERS[idx]
            text = _render(rng, rng.choice(BANKS[field][drawn]))
            per_field[field] = {"tier": drawn, "tier_noised": drawn != tier}

        texts[field] = _surface_noise(rng, text)

    truth = {"sentiment_z": round(z, 3), "tier": tier, "fields": per_field}
    return texts, truth
