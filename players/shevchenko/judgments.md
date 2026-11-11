# Andriy Shevchenko — judgment log (club SOC calculator)

Build: `python3 players/shevchenko/build_shevchenko.py` (reads `raw/`, `elo/ents.json`, `elo/opponent_elo_by_team_season.csv`, `elo/aliases.csv`; writes `shevchenko.json`, `src/data/she.js`). Options: `--debug` (Elo sources, Ukrainian model), `--fm` (FotMob goal check), `--cross` (teammate files).
Result: 648 games, 321 goals (PK 38), 85 assists, 48,455 minutes, 406 rows (74 two-leg rows in 52 games).
Verified in a scratch copy (add_players.py + manual seasonOf branch, build.py, verify.js check): existing 70 players unchanged, Shevchenko added, no console errors; `elo_table.js` → 0 conflicting team-seasons.
SOC 419.92 (29th of 71), best-3 46.11, best-5 43.07.

## 1. Scope
| item | decision | evidence / precedent |
|---|---|---|
| Dynamo Kyiv II (Dynamo-2), 56 games / 21 goals 1993-96 (UKR2 + Ukrainian Cup) | **excluded** | reserve team (Klose KL II, Musiala Bayern II …) |
| TM "played for a different team" Dynamo Kyiv games Aug–Nov 1994 (15: UKR1 10, CL 3, CLQ 2) | not counted | not `played` for the first team in TM API (he played for Dynamo-2) |
| National team (Ukraine A 111, U21 7) | excluded | standard |
| Soccer Aid (FotMob) | excluded | charity friendlies |
| Clubs | Dynamo Kyiv 1994-99 + 2009-12 (one key `dynsh`), Milan 1999-2006 + loan 2008-09 (one key `acmsh`), Chelsea 2006-08 + 1 game 2009-08-18 (`chesh`) | Immobile `torim` precedent for returning clubs |

Totals TM API = TM reports = en/uk Wikipedia: Dynamo 166+83 = 249 games / 124 goals, Milan 296+26 = 322 / 175, Chelsea 76+1 = 77 / 22.

## 2. Appearances / minutes
- TM API `played` + `playedMinutes` for all 648 games; no 90-minute estimates.
- Dates: TM report date (local) where a report is saved (399 games), otherwise the TM schedule date (all European, local).
- Wikipedia agrees on every club-season-category except the season label of the 2003-12-14 Intercontinental Cup (TM season "2003"; en.wiki 2003-04). The calculator splits by date → 2003-04, matching en.wiki.
- 2005-04-12 Inter–Milan (abandoned at 0-1 after ~73 min, awarded 0-3): TM 90 min kept (Kaká's file also has 90 for the same match).
- FotMob playerMatches not available for him → no minute cross-check.

## 3. Goals (321, PK 38)
- All TM report goals kept (report = API in every game). No own goals by him.
- PK = TM goal type "Penalty" (38 = TM API penGoals 38). One "Penalty rebound" goal counted as an ordinary goal.
- FotMob (2010-11 onward): 14 of his 22 goals have FotMob events; counts, scores-after and PK flags identical; minutes differ in 6 (TM 17/55/64/17/34/45+3 vs FM 16/56/63/18/33/45) → TM minute kept (Klose/Müller precedent). 8 goals are in games where FotMob returns "Data not found" (TM only). No FotMob-only goals.
- **2005-04-12 Inter–Milan CL QF 2nd leg** (match abandoned after flares at 0-1, UEFA awarded 0-3): goal 30' kept with in-play score 0-0 → 0-1 and tie first leg 2-0 (`[2,0,2,0,1,1]`). Same as Kaká's assist row for this goal (identical Elo 1845 / lv / tie) and the Drogba 2013 Beşiktaş, Del Piero 1994 CSKA, Totti 2004 Kyiv, Lucas Moura 2012 precedents (events that happened in play are used).
- Penalty shootouts (tm_shootouts.csv): 1998-08-26 Sparta (his kick saved), 2003-05-28 CL final (he scored the winning kick), 2003-08-03 Supercoppa, 2003-12-14 Intercontinental, 2005-05-25 CL final (his kick saved). Kicks are not goals; TM final scores including shootouts are not used (scores come from the event sequence). No goal of his in extra time.
- 1998-05-31 Ukrainian Cup final v CSKA Kyiv: TM gameState "extra_time" but all three goals (1', 33', 65') are in normal time and his minutes are 90 → nothing special.

## 4. Assists (85)
All assists are before 2014-08-01 → TM report single source (Klose/Insigne precedent). FotMob 2010-12 events carry no assist for any Shevchenko goal or for any goal he assisted, so they neither confirm nor contradict.

101 TM report assists to other scorers → 85:
- − 7 penalty won: 1995-08-09 81' (Pokhlebaev PK), 1996-03-23 51' (Pokhlebaev PK), 1997-04-10 30' (Rebrov PK), 1998-03-11 16' (Rebrov PK), **1998-06-08 27'** (Rebrov PK, TM assist type "Handball by Andriy Shevchenko" — the penalty source, not a pass), 2007-01-06 51' (Lampard PK, Macclesfield), 2011-05-01 24' (Gusev PK).
- − 8 "Shot on goal": 1996-11-03 23', 1998-06-08 42', 1998-07-11 71', 2003-09-16 67', 2006-04-04 88', 2008-09-18 45+1' (Jankulovski deflected shot), 2010-02-27 70', 2010-04-10 62'.
- − 1 assist to an opponent own goal: 1998-08-26 88' (Sparta's Gabriel OG; TM type "Shot on goal").
- Not an assist: **2000-03-24 Juventus 84'** — TM report lists Shevchenko as provider of his own penalty goal (self-assist; API 0).
- 7 blank-type TM assists kept (pre-gap rule, Klose precedent): 1996-03-18 39', 1996-04-22 26', 1997-05-20 70', 1997-08-13 76', 2003-04-23 30', 2007-01-23 69' (Lampard), 2012-05-10 16'.
- API (100: Dynamo 41 / Milan 46 / Chelsea 13) vs report (101): only 1998-06-08 differs (API 1, report 2 — both removed here).
- Per club after exclusions: Dynamo 16 + 14, Milan 40 + 3, Chelsea 12.

### Unconfirmed
All 85 assists are TM-only (no second per-match source was available: FotMob has nothing before 2010-11 and no assists for him in 2010-12; no match reports searched). The 6 post-2010 TM-only assists (2010-07-27 Zozulya, 2010-08-04 Garmash & Gusev, 2010-08-17 Gusev, 2011-08-13 Ideye, 2012-04-14 Corrêa, 2012-05-10 Milevskyi) are kept by the pre-2014 rule.

## 5. Cross-player consistency (no other files edited)
All shared rows identical (date, minute ±2, score, comp, Elo, lv, tie):
- Kaká → Shevchenko goals 16 (incl. 2005-04-12 30', 2008-12-03 77'), Shevchenko → Kaká goals 7.
- Drogba → Shevchenko 3, Shevchenko → Drogba 4; Lampard → Shevchenko 3, Shevchenko → Lampard 2; Robben → Shevchenko 2 (matched by date/minute — rob.js assist rows hold the TM assist type in the note field); Shevchenko → Ballack 1; Ronaldinho → Shevchenko 1 (2008-10-02 UEFA Cup Zürich).
- No "same match, different Elo/lv/comp" rows for any shared match.
- Only TM Shevchenko assist to a teammate goal removed here: 2007-01-06 Macclesfield 51' Lampard PK (penalty won). lam.js has the goal row only — not a conflict.
- **No mismatches found.**

## 6. Opponent Elo
Priority: same match in other players' data (90 rows) → team×season table (158) → direct estimate (25) → rank + league model (133).

### Ukrainian Premier League (new model, all lv "(추정)")
- Same regression as Turkey/Austria/Belgium/Switzerland/Sweden (§4): mean = 1473 + 23.33 × (3-season average UEFA country coefficient − 7.333), spread 119, standard rank curve.
- Ukraine yearly country coefficients (kassiesa.net, ccoef pages; start year → value): 1993 3.333 (method1, the only method for 1993-94), 1994 2.5, 1995 3.333, 1996 1.5, 1997 5.625, 1998 7.333, 1999 5.375 (method2, same as the Swedish COEF_X precedent), 2008 16.625, 2009 5.8, 2010 10.083, 2011 7.75, 2012 9.5 (method4, same as TR/BE/AT values — Turkey 2012 = 10.2 checked).
- **Calibration K = −73**: mean of (existing value − regression value) for the 8 Ukrainian team-seasons already in the team×season table in his 2009-12 seasons with a TM rank (Shakhtar 2009-10 1690 / 2010-11 1720, Dynamo 2009-10 1660 / 2010-11 1650, Metalist 2010-11 1560, Karpaty 2010-11 1450, Tavriya 2010-11 1440, Vorskla 2009-10 1440). Rationale: Ukraine's coefficient comes from two clubs; existing estimates put the league lower. Check: model 1997-98 1st = 1641 vs Del Piero's Dynamo Kyiv 1997-98 1640.
- Resulting league means: 1994-95 1300, 1995-96 1286, 1996-97 1310, 1997-98 1341, 1998-99 1371, 2009-10 1482, 2010-11 1413, 2011-12 1441. Bottom 1990s teams ≈ 1120–1180 (weak basis — flagged).
- Existing team-season values take precedence (Shakhtar, Metalist, Tavriya, Vorskla, Karpaty 2010-11).
- 3rd tier (Ukrainian Cup: Dynamo-3 Kyiv 1997-98, SK Odessa 1998-99 — not in the UKR2 tables): same-season mean − 324 (Turkish 3rd-tier precedent) = 1017 / 1047.
- `Dynamo-3 Kyiv` is written **`Dynamo Kyiv III`** in the rows: elo_table.js normalisation drops 1-digit tokens, so "Dynamo-3 Kyiv" merged with "Dynamo Kyiv" 1997-98 (Del Piero 1640) and produced a conflict.

### Other leagues
- Serie A 18-team seasons 1999-00..2003-04: SA18 table of Totti/Del Piero (7·9·12·16 = 1762·1728·1697·1645 midpoints); 20-team seasons from existing values.
- Serie B 1999-00 Atalanta (Coppa Italia): 3rd/20 (en.wikipedia 1999–2000 Serie B standings order) → 1578 + 51.24 × curve = 1637.
- Bundesliga/La Liga/Ligue 1/Eredivisie/Premier League/Portugal 1990s: same-season existing rank values from ents.json (Bayern 1994-95 6th 1797, Barcelona 1997-98 1st, Newcastle 1997-98 13th, Lens 1998-99 6th, Arsenal 1998-99 2nd, Real Madrid 1998-99 2nd, Bayern 1998-99 1st, Hertha 1999-00 6th, Sporting 2001-02 1st).
- Direct estimates (MAN): Aalborg 1995-96 4th 1480, Brøndby 1997-98 1st 1520 (= existing Brøndby 1995-96), Barry Town 1998-99 1200 (= TNS 2004-05 Welsh champion), Galatasaray 1999-00 1st 1680 (= existing 1998-99), Galatasaray 2000-01 2nd 1660, Beşiktaş 2000-01 4th 1620, Dinamo Zagreb 2000-01 1500, CSKA Sofia 2001-02 3rd 1450 (= existing 2010-11 3rd), BATE 2001 1450.
- `node tools/elo_table.js` in scratch: 0 conflicting team-seasons.

## 7. Competition codes / ties
- UKR1/IT1/GB1 = lg. Ukrainian Cup, Coppa Italia, FA Cup, League Cup: final df, semi dsf, QF dk (FA Cup "Sixth Round" and its replay "6th round deciders" = dk), earlier dc.
- Supercoppa, UEFA Super Cup, Community Shield = df; Intercontinental Cup 2003 = cwc.
- CL: group (incl. 1999-2003 second group stage "Group 2/3") clg, last 16 cl16, QF clk, SF clsf, final clf; CLQ (incl. 2010 play-off "Qualifying Round") clq.
- UEFA Cup: first round elq; second/third round, last 16 elk (Klose precedent for old 2nd round); SF elsf; 2008-09 group elg. Europa League 2010-12: group elg, "Second Round" (R32)/last 16/QF elk.
- Two-legged ties (`tie`, ko 0): UEFA ties (ag+ET, ≤2020-21), Coppa Italia (ag+ET), League Cup SF 2007 (ag+ET, ≤2017-18), Ukrainian Cup 1990s two-leg rounds (ag+ET assumed — not verified; noted in NOTE). First-leg scores from TM reports; legs he did not play: 1998-11-08 SK Odessa 2-4 (away), 2007-01-10 Wycombe 1-1 (away). 2003 Coppa Italia final 1st leg (two-legged final) = df with tie.
- No ET goals/assists → `et` 0 everywhere; no PEN_NO_ET game.

## 8. Seasons / clubs
- Keys `dynsh`, `acmsh`, `chesh` (unused). Boundaries: 1999-07-01 / 2006-07-01 / 2008-08-23 (loan) / 2009-07-01 (loan end) / 2009-08-29 (Dynamo transfer).
- **Dynamo Kyiv needs a 1 July split** (new seasonOf rule): the Ukrainian league opened on 1995-07-25, 1996-07-20, 1998-07-07, 2010-07-09, 2011-07-10 and the previous season ended in June (1998-06-12). The 10 July rule would put 1998-07-07 Karpaty and 2010-07-09 Obolon (goal) into the previous season; 1 August would misplace all July league/CLQ games. With 1 July every game matches the TM season label (checked: 0 differences). integration.json carries `"jul1":["dynsh"]`, which add_players.py ignores → the orchestrator must add the branch by hand (tested in scratch, inserted right after `if(club==="kobvl")return "2019";`):
  `if(club==="dynsh"){const s=d.slice(5)>="07-01"?y:y-1;return s+"-"+String(s+1).slice(2)}`
- Milan and Chelsea: default 1 August (Kaká `acmka`, Lampard/Drogba/Ballack Chelsea keys are default; no July games).

## 9. Honours (hon)
TM honours: UCL 02/03; USC 03/04; LG 03/04 Milan + Ukraine 94/95–98/99; DC FA Cup 2007, Coppa Italia 02/03, Ukrainian Cup 95/96, 97/98, 98/99; LC 2007; SC 04/05. Runner-up: UCL 04/05, 07/08 (he did not play the 2008 final; TM lists it), Intercontinental Cup 02/03 (Kaká format). Ukrainian Cup 10/11 runner-up not listed (precedent: only UCL/intercontinental). Awards: Ballon d'Or 2004; POY "2000 세리에A 외국인 선수" (TM "Best foreign player"); FOY 6 (TM club text: 1997/1999/2000/2001 "Dynamo Kyiv" — he was at Milan for 2000/2001 and from mid-1999; kept TM literally); TOP 8 club entries (World Cup qualifiers top scorer excluded). TOP 94/95 Ukrainian Cup 6 goals includes Dynamo-2 cup goals (calculator: 1) — noted in NOTE.

## 10. Checks (§16)
Duplicates 0; score order OK; minutes in range; every E date in M with the same opponent/comp; every assist has a scorer name; no tie row with ko=1; NOTE free of code names.

## (통합 단계) 수상
- 우크라이나 올해의 선수 2000·2001은 그해 소속(AC 밀란)으로 고침(Transfermarkt는 디나모 키이우로 표기). 1999는 시즌 중 이적이라 Transfermarkt 표기 그대로.
