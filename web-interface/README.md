# Interfață web feedback — Flask

Dashboard peste rezultatele de feedback: cascadă de filtre derivată din arborele real de
categorii Moodle, clasamente, detaliu pe curs, și comentariile la întrebările deschise cu
sentiment estimat.

Documentația care contează:
[`docs/spec-general.md`](docs/spec-general.md) (arhitectură, decizii, contract) și
[`docs/data-layer-decisions.md`](docs/data-layer-decisions.md) (de ce stratul de date arată
așa). `docs/index.html` din rădăcina repo-ului e planul inițial — **depășit**, păstrat ca
istoric.

## Rulare

```bash
cd web-interface
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Nu are nevoie de nimic altceva. Fără date, aplicația cade pe un dataset sintetic
determinist și pornește.

## De unde vin datele

**Structura e reală** — cicluri, domenii, specializări, ani, semestre, serii, cursuri — și e
derivată din arborele de categorii Moodle (`taxonomy.py`). Cascada de filtre e construită din
ea, deci nu poți compune un scop contradictoriu.

**Conținutul nu e real.** Note, cadre didactice, înscriși, comentarii — toate sunt fabricate.
Nu avem acces la răspunsurile reale ale studenților. Există două surse de conținut fals, și
niciuna nu se dă drept adevărată:

- **fără niciun export** → scoruri generate determinist din id-ul cursului (`_hashf`), plus
  comentarii dintr-un corpus mic (`models/demo_comments.json`);
- **cu un export din `generate-feedback/`** → `feedback_contents/` + `users/`, exact formatul
  pe care l-ar avea un export real din Moodle.

```bash
# generezi un dataset complet și îl dai interfeței
cd ../generate-feedback && python3 convert_script.py && python3 main.py --seed 1
cd ../web-interface
FEEDBACK_DATA_DIR=../generate-feedback/out flask --app app run
```

(Pickle-urile trebuie să stea lângă `feedback_contents/` și `users/`; interfața ignoră
exportul dacă lipsește vreunul din cele două directoare.)

## Badge-urile — regula, nu decorul

Trei badge-uri, trei întrebări diferite:

| Badge | Răspunde la |
|---|---|
| ✓ **date reale** | structura vine din arborele Moodle real |
| ⚠ **date demonstrative** | cifrele nu sunt reale |
| ⚗ **sentiment estimat** | eticheta e ghicită de un model, nu declarată de student |

Badge-ul demonstrativ **nu dispare doar fiindcă există un export de conținut**. Generatorul
produce un export perfect valid și complet inventat; dacă simpla lui prezență ar stinge
badge-ul, interfața ar prezenta drept reale niște note și niște nume născocite. Regula e
*fail-closed*: conținutul e considerat real doar dacă cineva declară explicit
`FEEDBACK_CONTENT_SYNTHETIC=0`, iar un export care se declară singur sintetic (prin
`manifest.json`) nu poate fi promovat nici așa.

Badge-ul de model rămâne aprins **și** peste date reale — atunci contează cel mai mult să știi
că eticheta e o presupunere.

## Structura

| Fișier | Ce face |
|---|---|
| `app.py` | Rutele. Importă **doar** din `queries.py`. |
| `queries.py` | Contractul de date. Nu importă niciodată flask. Testat coloană cu coloană în `tests/test_contract.py`. |
| `taxonomy.py` | Arborele de categorii → cascadă, cursuri, serii; adaptorul de conținut; proveniența (fail-closed) și pragul comentariilor. |
| `aggregates.py` | Clasamente și distribuții peste substratul taxonomiei. |
| `mocks.py` | Doar Sumarul și acoperirea — cifre transcrise din deck, nerecalculabile din datele pe care le avem. |
| `comments.py` | Textul liber: redactare de nume, separare pe întrebări, ruperea legăturii cu autorul. |
| `sentiment.py` | Naive-Bayes din biblioteca standard; greutățile sunt antrenate offline și livrate în `models/`. |
| `tools/train_sentiment.py` | Antrenorul (offline; aplicația nu-l importă niciodată). |
| `templates/`, `static/` | Jinja + htmx (`hx-boost`), zero JS scris de mână. Temă light/dark/auto pe tokeni `light-dark()`. |

## Comentarii și confidențialitate

Cele patru întrebări deschise sunt singurul loc unde apare text scris de un student, și au un
prag propriu: **sub 5 răspunsuri, un curs nu afișează niciun comentariu.** Anonimatul Moodle e
la nivel de *răspuns* — elimină autorul, nu conținutul — iar numele titularului și al
asistentului se află în același rând cu comentariul. Pragul e fix în codul stratului de date,
nu în template: exportul CSV re-emite toți parametrii din URL, deci o verificare în view ar
fi ocolită de `?export=csv`.

În plus: numele complete ale cadrelor sunt eliminate din text, iar cele patru răspunsuri ale
unui student sunt reordonate independent, ca să nu poată fi puse la loc cap la cap. Detalii și
limite — pagina `/despre-date`.

## Teste și CI

```bash
pytest tests/ -q          # conftest forțează datasetul sintetic
ruff check . && ruff format --check .
```

CI rulează exact astea două pe orice push care atinge `web-interface/`.

## Demo public (Render)

`render.yaml` (rădăcina repo-ului) publică interfața ca demo. Exportul real nu ajunge nici în
repo, nici pe host, deci demo-ul rulează pe datele sintetice și își spune asta prin badge.

Plan free: adoarme după inactivitate, primul request după pauză durează ~30s.
