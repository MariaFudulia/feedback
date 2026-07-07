# Interfață web feedback — Streamlit

Vezi `web-interface-plan-v2.docx` (rădăcina repo) pentru planul complet. Rezumat aici doar
pentru pornire rapidă.

## Rulare

```bash
cd web-interface
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Chiar acum, tot ce vezi rulează pe **date mock** din `mocks.py` (numere reale din deck-ul
coordonatorului, acolo unde slide-ul a fost lizibil — vezi comentariile din `mocks.py` pentru
cele câteva serii care sunt doar placeholder de formă). Nimeni nu așteaptă baza de date reală
(PR #3, încă open) ca să înceapă.

## Cum lucrăm în paralel, de azi

Regula de bază: **toate paginile importă doar din `queries.py`**, niciodată din `mocks.py`
direct. Asta e contractul — semnăturile din `queries.py` sunt fixate, restul poate schimba.

- **Coleg A — strat de date**
  `db/init.sql` (schema PR #3, deja copiată aici) → `db/make_fixture.py` (bază SQLite mică, de
  test) → înlocuiește corpul fiecărei funcții din `queries.py` cu interogări SQL reale peste
  fixture, apoi peste `moodle_analytics.db` când PR #3 face merge. Portează pragurile de
  selecție din `analysis/` (curs ≥7%&≥3fb · titular mediu≥7%&≥15fb · asistent≥10fb) — sunt deja
  aplicate în `mocks.py` ca referință de comportament așteptat.

- **Coleg B — shell, filtre, sumar**
  `sidebar.py` (filtre în cascadă), `app.py` (pagina Sumar — slide 3),
  `pages/1_Completare_si_evaluare.py` (slide-uri 4, 5, 6).

- **Coleg C — clasamente și ani de studiu**
  `pages/2_Pe_ani_de_studiu.py` (slide-uri 7-9), `pages/3_Top10_Cursuri.py`,
  `pages/4_Top10_Titulari.py`, `pages/5_Top10_Asistenti.py` (slide-uri 10-16),
  `pages/6_Evaluare_pe_zone.py` (slide-uri 17-19).

Niciunul dintre B și C nu așteaptă pe A — deja rulează pe mock. Când A termină o funcție reală,
nimic din B/C nu se schimbă (aceleași coloane, același nume de funcție).

## Workflow Git

Branch propriu per coleg (`username-a/...`, `username-b/...`, `username-c/...`), NU pe main.
Draft PR devreme. Merge-uiește când pagina ta rulează fără erori pe mock.

## De clarificat cu coordonatorul (nu blochează codul de mai sus)

- Sursa lui `num_utilizatori` (enrolment) — nu există în schema DB din PR #3.
- Ce se întâmplă cu PR #20 (Vlad, Flask, doar „Hello World") — se abandonează sau se
  redenumește branch-ul spre acest plan.
