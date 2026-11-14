# Filippo Inzaghi — judgment log (club SOC calculator)

Build: `python3 players/inzaghi/build_inzaghi.py` (reads `raw/`, `elo/*`, teammates' `src/data/*.js`; writes `inzaghi.json`, `src/data/inz.js`). Options `--debug` (Elo sources), `--fm`, `--cross`.
Result: 623 games, 288 goals (PK 15), 43 assists, 42,912 minutes, 331 rows (59 two-leg rows in 41 games). SOC 442.08 (25th of 81), best-3 50.04, best-5 43.84.
Verified in scratch copy (add_players.py + build.py + verify.js check): existing 80 unchanged, Inzaghi added, no console errors; elo_table.js: 0 conflicting team-seasons.

## 1. Scope / clubs
- Excluded: Milan Primavera 2011-11-12 (youth), Italy U21/A. Leffe Coppa Italia Serie C (it.wikipedia only, 0 goals) not in TM -> not added. it.wikipedia career total 624/291 vs sum of its club totals 624/288.
- Brief said Leffe C2 / Verona 1992-93 / Piacenza 1993-95; TM, en and it Wikipedia all say Leffe 1992-93 (C1), Verona 1993-94, Piacenza 1994-95 -> sources followed. Keys: piaiz (1991-92 and 1994-95, one key), lefiz, veriz, pariz, atliz, juviz, acmiz. Boundaries = TM transfer dates (1992-07-01, 1993-07-01, 1994-07-01, 1995-07-01, 1996-07-01, 1997-07-01, 2001-07-02).
- Leffe 1992-93 C1/A: TM table 18 teams (34 rounds); TM schedule lists only 32 Leffe games (rounds 7 and 24 absent). Table top (Ravenna 1, Vicenza 2, Empoli 3, Triestina 4, Leffe 5 (36 pts), Como/Chievo 6-7) confirmed by it.wikipedia Serie C1 1992-93 search snippet; no Inzaghi G/A in the missing slots. n=18 kept.

## 2. Minutes / goals
- TM API played + playedMinutes for all 623 (no estimates); TM = en.wikipedia per club-season-category (0 diffs). FotMob only 2010-12: 5 goals identical (minute, score).
- 2012-01-18 Novara (Coppa Italia, AET): TM 59', FotMob lineup lacks him; TM kept (no G/A).
- 1022468 Milan-Reggina 2002-11-03 20': 'Penalty rebound' -> ordinary goal (PK flag 0). PK = TM 'Penalty' 15 = API penGoals 15.
- 2003-02-22 Torino-Milan (TM 'suspended', 63'): 0-3 result was ratified (Italian sources via search: result homologated, not a 0-2 table award; abandonment 63' or 64'). Goal 2' (0-0 -> 0-1) kept, minutes 63.
- Shootout games (2003 CL final, 2003 Supercoppa, 2003 Intercontinental): no G/A; Inzaghi not a taker.

## 3. Assists (43)
TM 56 = Pass 31, Penalty-fouled 10, Header 5, Shot on goal 3, Cross 2, untyped 5. Excluded: 10 PK-won (7 Del Piero 1998-01-11, 1998-04-01, 2000-01-09, 2000-01-16, 2000-02-20, 2000-03-05, 2001-04-08; Rivaldo 2003-02-25; Pirlo 2004-02-08; Rui Costa 2006-01-11), 2 shot rebounds (Shevchenko 2002-05-05 49', Kaká 2006-04-09 62'), 1 opponent OG (Bari 1998-02-28 19', also 'Shot on goal'). Self-assist 990059 (2000-09-13 Hamburg 88' PK) not an assist. All pre-2014-08 -> TM single source (Klose/Insigne precedent); 5 untyped kept (1997-01-05 Magallanes, 1997-01-26 Foglio, 2003-02-19 Tomasson, 2003-04-23 Shevchenko 65', Tomasson 90').
- 2010-11-03 Real Madrid 68': FotMob assist Ibrahimovic, TM none. ibr.js NOTE explicitly excludes this FotMob-only assist (ESPN none) -> no assist here; consistent.
- 2012-05-13 Novara 82': TM Seedorf (Pass), FotMob none. Kept (pre-2014 rule). A web search summary (Il Giorno/ANSA/acmilan.com snippets) says Seedorf's through ball; page fetch was blocked in this session, so only the search summary. Seedorf's own file (see.js, parallel judge) already contains it with identical row.
- Unconfirmed: all 43 are TM-only except Catania 2010-09-18 (Ronaldinho) and Real Madrid 2010-11-03 78' (Gattuso) which FotMob confirms.

## 4. Competition codes / ties
- Serie A/B/C1 lg. Coppa Italia: first rounds/R16 dc, QF dk, SF dsf, final df (2003 final two legs both df + tie). Supercoppa/UEFA Super Cup df. Intercontinental Cup 2003 and Club World Cup 2007 cwc (2007 final ko 1). CL group (incl. 2002-03 'Group 3') clg, R16 cl16, QF clk, SF clsf, final clf; CLQ clq. UEFA Cup first round elq, later rounds elk, SF elsf. Cup Winners' Cup 1995-96 (Parma, Teuta first round, Halmstad R16) elk (Ronaldo/Nedved precedent). Intertoto 1999 (SF, final) elq (Del Piero/Lampard precedent).
- ITPO 1998-99 UEFA Cup play-off Juventus-Udinese (0-0 in Udine 1999-05-28; 1-1 Turin 1999-05-31, Inzaghi PK 23', Poggi 71'; Udinese through on away goals, no extra time): lg (Ronaldo ITPO / Mertens PONL precedent) + tie [2,1,0,0,1,0] (ag 1, et 0). Source: search results (udinese.it, besoccer, myjuve.it, calciostyle). Only this one row.
- Other legs: tm_two_leg_ties.csv + match_info; all 59 tie rows ag 1 / et 1 (UEFA, Intertoto, Coppa Italia <=2021-22). Single-leg Coppa Italia first rounds ko 1.

## 5. Seasons
juviz = 10 July (Intertoto 1999-07-28/08-04 = 1999-00; Del Piero juvdp/Zidane juvzd precedent) -> integration `jul10: ["juviz"]`. Others default 1 August (2003-08-03 Supercoppa, 2006-08-09 CLQ new season). Checked against TM season labels: only difference is the 2003 Intercontinental Cup (TM '2003', no G/A). No special seasonOf branch needed.

## 6. Elo
Priority: same match in other players (148 rows) -> team-season table (119) -> direct estimate (6) -> rank + model (58).
- Serie A 18-team 1995-96..2003-04: SA18 (existing, midpoints 7/9/12/16 = 1762/1728/1697/1645); 20-team seasons existing values.
- Serie B (1993-94, 1994-95, 1999-00 Napoli 2nd, 2005-06 Brescia 10th/22): mean 1577.78, SD2 51.24 curve (reproduces existing 20/22-team values).
- Serie C1 1992-93 A (8 Leffe opponents), Ars et Labor 1996-97 (15th/18, A), Novara 2009-10 (1st/18, 'Lega Pro 1' label as Insigne/Cavani): mean 1416.56 (Insigne value; reproduces Totti/Del Piero values), SD2 51.24, all '(추정)'. Weak basis.
- Direct estimates: Halmstads 1995 3rd/14 1439 (= Allsvenskan 2001 3rd, Nedved interpolation method; Wikipedia rank), Teuta 1995-96 2nd 1300 (= KF Tirana 2009-10 3rd; Wikipedia rank), Panathinaikos 2000-01 2nd 1560 (= 2001-02 2nd), Slovan Liberec 2002-03 4th 1480 (**matches the parallel Seedorf file, which had already used 1480 and the same lv text**).
- Boca Juniors 2003 / Hellas Verona Primavera: no G/A row -> no Elo needed.
- elo_table.js (scratch, with Inzaghi, other parallel files removed): 0 conflicts.

## 7. Cross-player (no other file edited)
All shared rows identical (date, minute, score, comp, Elo, lv, tie): Del Piero (assists to/from, same-match), Zidane, Shevchenko, Kaká, Henry, Seedorf (see.js), Ronaldinho; ~195 same-match comparisons same. Dropped assists (PK/rebound) have goal rows only in teammates' files, no conflict.

## 8. Honours (TM achievements)
UCL 02/03, 06/07; USC 03/04, 07/08; CWC 07/08 (TM '2008'); LG 97/98 Juventus, 03/04, 10/11; DC 02/03; SC 97/98, 11/12; o: UCL runner-up 97/98, 04/05, Intercontinental runner-up 02/03, Serie B champion 94/95 Piacenza, Intertoto 99/00; a: TOP 96/97 Serie A 24. Omitted: World Cup 2006, Euro 2000 runner-up, U21 Euro 1994, 'Best young player 1997' (no column).

## 9. Checks (§16)
Duplicates 0; score order OK; minutes in range; every E date in M with same opponent/comp; assist scorer names present; no tie row with ko=1; NOTE free of code names.
