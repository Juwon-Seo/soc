# Miroslav Klose — judgment log (club SOC calculator)

Build: `python3 players/klose/build_klose.py` (reads `raw/`, `elo/ents.json`, `elo/opponent_elo_by_team_season.csv`; writes `klose.json`, `src/data/klo.js`).
Result: 618 games, 232 goals (PK 9), 105 assists, 43,993 minutes. Verified in a scratch copy: existing 55 players unchanged, Klose added, no console errors, `elo_table.js` conflicts 0.

## 1. Scope
| item | decision | evidence / precedent |
|---|---|---|
| FC 08 Homburg 1998-99 (18 games, 1 goal, RL West/Südwest = 3rd tier) | **included** | first team, official league. Precedent: lower-tier first teams are included (Reus Ahlen Regionalliga Nord, Ribéry Boulogne/Alès, Immobile Sorrento) |
| 1. FC Kaiserslautern II (50 games, 26 goals, RWS 1999-00 + OL8 2000-01) | **excluded** | reserve team; every precedent excludes reserve/B teams (Musiala Bayern II 3. Liga, Lewandowski Legia/Znicz II, Benzema/Henry/Mbappé/Hazard 2군, Isco Mestalla, Silva/Villa B …). Removes the 2000 KL/KL II overlap: one club key per date is possible |
| FC 08 Homburg Amateure (de.wiki 15 g 10 goals), Blaubach-Diedelkopf | excluded | no match data in TM; amateur/reserve |
| TM "played for a different team" (5 games 2000-05..09) | not counted | not `played` in TM API |
| Friendlies, national team | excluded | standard |

## 2. Appearances / minutes
- TM API `played` + `playedMinutes` for all 618 games (no 90-minute estimates needed).
- en.wikipedia agrees on apps/goals per club-season-competition except Lazio 2015-16 Europe (TM 5, wiki 4). All five TM games (CLQ 2015-08-18 Leverkusen 45', EL Dnipro, Galatasaray ×2, Sparta 2nd leg) show Klose in the TM report substitution list → **5 kept** (no goal/assist; minutes only). Which game wiki omits is not determinable from the sources here (likely the CL qualifier).
- en.wiki Bayern total "149" is an internal inconsistency (components = 150 = TM).
- Dates: TM report date (local); games without report: UTC → Europe/Berlin.

## 3. Goals
- 232 = TM report goals for included clubs (Homburg 1, KL 52, Werder 63, Bayern 53, Lazio 63).
- 2002-11-17 Werder–KL 61': TM report = Klose **own goal** → not a goal (API 0 too).
- PK goals per TM (9): 2002.4.21, 2003.2.8, 2003.3.9, 2003.4.27, 2003.10.19, 2006.4.1, 2008.8.31, 2009.3.10, 2016.5.15. FotMob agrees for the 2010+ games.
- FotMob check (2010-11 onward): 69 of 71 goals have FotMob events; score/PK identical; minute differs in 11 (1–3 min, incl. 2 where FotMob writes 90 for 90+x) → TM minute kept (Müller precedent). No FotMob: 2010-08-07 DFL-Supercup (not in FotMob), 2011-01-29 Werder–Bayern (FotMob "Data not found").
- Stoppage time: 45+1 → 46 with dm "45+1"; 90+x → 90+x with dm. ET goals keep the real minute (102, 105).

## 4. Assists (105)
Rule applied (docs §3, Müller/Reus precedent): before 2014-08-01 TM report assists minus exclusions; after, TM ∩ FotMob (±2 min), TM-only needs two further sources, FotMob-only not added unless two sources.

141 TM report assists (club teams in scope) → 105:
- − 22 penalty won ('Penalty: Fouled player'): 2000.10.14 14', 2000.11.9 25', 2001.3.3 52', 2001.10.20 82', 2002.5.4 44', 2002.11.17 18', 2003.10.19 62', 2005.12.7 2', 2005.12.21 83', 2006.3.4 3', 2006.4.1 70', 2008.2.27 120+2', 2009.3.10 82', 2012.3.4 10', 2012.9.30 38', 2013.1.5 86', 2013.8.25 16', 2014.1.19 63', 2014.1.25 27', 2015.1.14 57', 2015.2.15 23', 2016.1.17 71' (the 2003.10.19, 2006.4.1, 2009.3.10 ones are Klose's own PK goals; 2008.2.27 = Ribéry PK)
- − 10 'Shot on goal': 2006.5.13 27', 2006.12.9 86', 2007.1.28 74', 2007.7.21 24', 2007.11.10 86', 2008.2.21 71', 2008.10.25 54' & 63', 2013.5.12 10', 2014.8.24 79'
- − 3 assists to opponent own goals: 2002.1.26 76' (Pletsch), 2006.4.8 33' (Schweinsteiger OG for Werder), 2012.3.11 56' (Rubin)
- − 1 post-gap TM-only: 2015.4.12 Empoli 53' Felipe Anderson (TM 'Cross', FotMob none; reports via WebSearch describe Klose's low cross parried by Sepe and Anderson tapping in the rebound → not confirmed as an assist).
- **29 blank-type TM assists kept** (2000–2007 + 2009.3.10 74' + 2014.11.3 7'); pre-gap rule = TM, and blank type is how TM lists older assists. 2014.11.3 is also confirmed by FotMob.
- API vs report: 2002.11.17, 2003.10.19, 2006.4.1 differences are PK-won rows (excluded anyway). 2009.3.10: report 74' (blank, van Bommel) + 82' (PK won); API 1 → 74' kept.
- Post-gap TM∩FotMob: the 12 remaining post-gap assists (2014.9.14, 2014.11.3, 2015.1.24, 2015.3.16, 2015.5.25, 2015.10.25 ×2, 2016.1.17 77', 2016.2.11, 2016.4.3, 2016.4.10, 2016.4.17) are all FotMob assist events too. FotMob Serie A season totals 2014-15 = 7, 2015-16 = 7 reconciled (see below).
- FotMob-only (not added): 2015.3.1 Sassuolo 77' Parolo (TM: Maurício 'Shot on goal'; worldfootball: Cataldi; no source credits Klose); **2014.12.21 Inter 37' Felipe Anderson** (found by fetching FotMob matchDetails for all 42 remaining post-gap Lazio games — this explains FotMob's 7th 2014-15 assist; reports describe Anderson's solo run, no Klose credit).
- 2011.8.18 Rabotnički: TM 3 assists kept (pre-gap); en.wiki text says 4, FotMob events 0.
- Sources not reachable: fbref/worldfootball (blocked). WebSearch summaries used for the 3 post-gap cases only.

### Unconfirmed (kept by rule, single source TM)
All 93 pre-2014-08 assists (105 − 12) are TM-only (FotMob has no/unreliable Klose assist data before 2014; no fbref/worldfootball access). This is the docs' standard pre-gap treatment, but none was independently re-checked here (Ribéry's file shows such checks can remove some — see §5).

## 5. Cross-player consistency (no other files edited)
- Rows in other files naming Klose as assist provider target: 14 Ribéry + 2 Müller rows (Klose goals assisted by them). All 16 match a Klose goal row exactly (date, minute, score before, comp, Elo, lv).
- Klose assists to calculator players: Ribéry 2007.10.20 35', 2008.3.19 60', 2008.10.29 70', 2010.8.16 45+1', 2011.5.7 88'; Müller 2009.10.28 29', 2010.8.7 75' — all have matching goal rows (min, score, Elo, comp).
- TM assists by Ribéry on Klose goals that Ribéry's file deliberately removed (documented in RIB_NOTE): 2008.11.25 57' (UEFA/club report: no assist), 2010.12.22 52' (no assist in reports), 2010.12.22 86' ('Shot on goal'). Klose's goals unaffected; not a conflict.
- **Mismatch to flag**: rib.js codes 2007-07-21 Werder–Bayern DFB-Ligapokal as `df` (final), but TM report round = "intermediate stage" (the quarter-final; final was 2007-07-28 vs Schalke). Klose's M row for that date uses `dk`. Ribéry's NOTE says "리가포칼 준결승·결승은 국내컵 준결승·결승" — so `df` there looks like an error (affects Ribéry's 2 goals + 1 assist that day). Not changed.
- Same-match Elo reuse: 45 rows took Ribéry/Müller values (Burghausen 1420, Wuppertal 2008 1420, Steaua 1450 'FCSB' alias, Lyon 1825, Sporting 1786, Windeck 1180 …).

## 6. Opponent Elo
Priority: same match in other players' data (45 rows) → team×season table (106) → rank + league model (160) → direct estimates (26).
- Bundesliga 2000-01..2006-07: 18-team mapping = 2025-26 values (1:2006 … 18:1613), confirmed from ents lv texts for 1999-00, 2000-01, 2001-02, 2002-03, 2004-05..2006-07.
- Bundesliga 2007-08..2009-10: existing seasons are the base minus a constant (2007-08 −65.5, 2008-09 −34, 2009-10 −33). Missing ranks filled with that shift: 2007-08 7th Leverkusen 1712, 2008-09 11th Hannover 1679 / 14th Bochum 1648, 2009-10 11th Hoffenheim 1680. 2010-11 all from table.
- Serie A: fixed 20-team mapping (1:1969 … 20:1614); all Lazio-era league rows via table/rank.
- 2. Bundesliga: no seasonal shift in existing data; curve fitted to existing values (3rd 1636 … 18th 1532, max error 1) → 1st 1697 (Gladbach 2007-08), 4th 1622 (Mainz 2001-02), 9th 1584 (Waldhof 2001-02).
- Eredivisie 2006-07 3rd AZ 1677 (constant across 2000-01..2002-03 data).
- Estimates (lv "(추정)"): German 3rd-tier Regionalliga 1450 (Reus precedent "3. 리가 이전 포함"): Wuppertal 1998-99, Braunschweig 2003-04, Bayern II 2004-05, St. Pauli 2005-06. Note: Ribéry/De Bruyne use 1420 for 3rd tier 2007-08 (Burghausen, Wuppertal) — those same matches reuse 1420. 4th tier Paloma Hamburg 2002-03 1300. 3. Liga Erfurt 2008-09 10th 1422 (interpolated between existing 9th 1429 / 13th 1409). Bohemian 2000 1300, Iraklis 2000 1480, Rangers 2000 1620, Slavia 2001 1500, Teplice 2003 1400, Anderlecht 2004-05 1596, Basel 2005 1600, Red Star 2007 1500, Braga 2007-08 7th 1606 (Portuguese 16-team curve fitted to existing values), Aberdeen 2007-08 1500, Rabotnički 2011 1300, Mura 2012 1300, Bassano 2014-15 (Lega Pro A 2nd) 1490.
- `node tools/elo_table.js` on the scratch copy: 0 conflicting team-seasons.

## 7. Competition codes / ties
- DFB-Pokal, Coppa Italia: dc (≤R16) / dk / dsf / df; round from report, else API gameDay.
- DFB-Ligapokal: "intermediate stage" (first match, QF-level) = dk, semi = dsf, final = df, ko 1 (Ribéry precedent for semi/final).
- DFL-Supercup 2010, Supercoppa 2013/2015 = df.
- UEFA Cup: 1st round = elq (docs §3); old-format 2nd round (2000-01 Iraklis) = elk (Ronaldinho 2001-10-18 Rapid precedent; docs only say 3rd round~QF); 3rd round/last 16/QF = elk; SF = elsf; 2007-08 group = elg. EL "Second Round"/"intermediate stage" (R32) = elk; ELQ playoff = elq. CL: clq/clg/cl16/clk/clsf/clf.
- Two-legged ties (`tie`): UEFA KO & qualifiers and Coppa Italia SF; ag=1 (UEFA ≤2020-21, CIT ≤2021-22), et=1. First-leg scores from the first-leg TM report (all present; 9 legs Klose didn't play listed in NOTE). ko=0 on tie rows (precedent).
- ET: 2003-02-05 102' assist and 2005-10-25 105' goal (single KO, min > 95 → ET automatically). No ET goal at 91–95 needed the `et` flag.

## 8. Seasons / clubs
- Keys: homkl, fckkl, svwkl, baykl, lazkl (unused in index.html). Boundaries 1999-07-01 / 2004-07-01 / 2007-07-01 / 2011-07-01.
- July-10 rule for fckkl (2000-07-27 Ligapokal → 2000-01), svwkl (2005-07-23 → 2005-06), baykl (2007-07-21 → 2007-08) — same as Ribéry bayr/Müller bayt. Homburg, Lazio: default Aug 1.
- Resulting seasons match en.wiki season rows (e.g. KL 2000-01 45 games incl. Ligapokal 2).

## 9. Honours (hon)
TM honours (titles only): LG 07/08, 09/10 Bayern; DC 07/08, 09/10 Bayern, 12/13 Lazio; LC "2007" Werder, "2008" Bayern (TM labels); SC 10/11 Bayern; awards FOY 2006 (Werder), POY 05/06 Bundesliga, VDV 05/06, TOP 05/06 Bundesliga 25 goals. Runner-up: UCL 09/10 Bayern (precedent: only UCL finals listed). Excluded: World Cup 2014, World Cup top scorer 2006.

## 10. Tool issue found
`tools/add_players.py`: with more than one `season.jul10` key the second `rep()` fails (anchor `||club==="lhma"){` is consumed by the first replacement) → "앵커 개수 불일치(0≠1)". In the scratch copy I changed the loop to insert all jul10 keys in one replacement; the repo file is untouched.
