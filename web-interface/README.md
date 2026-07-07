# Interfață web feedback — Flask

Vezi `docs/index.html` (rădăcina repo) pentru planul complet — obiective, arhitectură,
contractul de date, împărțirea muncii. Rezumat aici doar pentru pornire rapidă.

## Rulare

```bash
cd web-interface
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Chiar acum, tot ce vezi rulează pe **date mock** din `mocks.py` (numere reale din deck-ul
coordonatorului, acolo unde slide-ul a fost lizibil — vezi comentariile din `mocks.py` pentru
cele câteva serii care sunt doar placeholder de formă). Nimeni nu așteaptă baza de date reală
(PR #3, încă open) ca să înceapă.

## Cum lucrăm în paralel, de azi

Regula de bază: **rutele Flask importă doar din `queries.py`**, niciodată din `mocks.py`
direct. Asta e contractul — semnăturile din `queries.py` sunt fixate, restul poate schimba.

- **Coleg A — strat de date**
  `db/init.sql` (schema PR #3, deja copiată aici) → `db/make_fixture.py` (bază SQLite mică, de
  test) → înlocuiește corpul fiecărei funcții din `queries.py` cu interogări SQL reale peste
  fixture, apoi peste `moodle_analytics.db` când PR #3 face merge. Portează pragurile de
  selecție din `analysis/` (curs ≥7%&≥3fb · titular mediu≥7%&≥15fb · asistent≥10fb) — sunt deja
  aplicate în `mocks.py` ca referință de comportament așteptat.

- **Coleg B — shell, filtre, sumar**
  `app.py` (rute + shell), `templates/base.html` (layout comun), `templates/sumar.html`
  (slide 3), `templates/completare_evaluare.html` (slide-uri 4-6).

- **Coleg C — clasamente și ani de studiu**
  `templates/pe_ani_de_studiu.html` (slide-uri 7-9), `templates/top10_cursuri.html`,
  `templates/top10_titulari.html`, `templates/top10_asistenti.html` (slide-uri 10-16),
  `templates/evaluare_pe_zone.html` (slide-uri 17-19).

Niciunul dintre B și C nu așteaptă pe A — deja rulează pe mock. Când A termină o funcție reală,
nimic din B/C nu se schimbă (aceleași coloane, același nume de funcție).

Există deja un schelet Flask funcțional (cele 7 rute de mai sus răspund 200,
`tests/test_smoke.py`) — minimal: formulare simple, fără filtrele în cascadă complete.
Fiecare completează partea lui peste ce există deja.

## Workflow Git

Branch propriu per coleg (`username-a/...`, `username-b/...`, `username-c/...`), NU pe main.
Draft PR devreme. Merge-uiește când pagina ta rulează fără erori pe mock.

## De clarificat cu coordonatorul (nu blochează codul de mai sus)

`num_utilizatori` (enrolment) e rezolvat pe partea de CSV: `dump_enrolled_users.py` +
`mappings/num_students_per_course` produc `num_users.csv`. Nu apare în schema DB din PR #3,
deci rămâne de adăugat acolo dacă trecem pe bază de date.

PR #20 (Vlad, Flask „Hello World") — acum că mergem tot pe Flask, merită văzut cu Vlad dacă
branch-ul ăla se coordonează cu munca de aici, sau rămâne separat.
