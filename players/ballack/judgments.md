# Michael Ballack — judgment log (club SOC calculator)

Build: `python3 players/ballack/build_ballack.py` (reads `raw/`, `elo/ents.json`, `elo/opponent_elo_by_team_season.csv`; writes `ballack.json`, `src/data/blk.js`).
Result: 587 games, 144 goals (PK 17), 75 assists, 46,003 minutes. SOC 252.96, best-3 35.27, best-5 30.26.
Verified in a scratch copy (tools/add_players.py etoo + build + verify check): existing 60 players unchanged, Ballack added, no console errors; `elo_table.js` → 0 conflicting team-seasons (61 players).

## 1. Scope
| item | decision | evidence / precedent |
|---|---|---|
| Chemnitzer FC 1995-97 (51 g, 10 goals; 2. Bundesliga 1995-96, Regionalliga Nordost 1996-97 = 3rd tier, DFB-Pokal 2) | **included** | first team, official. Klose Homburg (RL West/Südwest) precedent |
| 1. FC Kaiserslautern II 1997-98 (17 g, 8 goals, TM level=reserve, club 151) | **excluded** | reserve team (all precedents; Klose KL II) |
| Chemnitzer FC II (wiki 18 g 5 goals Oberliga) | excluded | no TM match data, reserve |
| 7 KL-II dates "played for a different team" | not counted | not `played` |
| 1997-08-16 DFB-Pokal KL (first team) at KL II | included (first-team game, opponent = reserve) | TM club id 2 |
| Saxony Cup 96/97 | no games in TM; honour not listed (regional cup) | |

## 2. Appearances / minutes
TM API `played` + `playedMinutes` for all 587 (no 90-min estimates). en.wikipedia apps/goals identical for every club-season-category (raw/tm_vs_wiki_en.csv). de.wikipedia Chelsea 166/25 (2006-07 league goals 4, 2007-08 apps 29) — noted, TM/en kept. Dates = TM report date (local). 990077 (2000-09-20 Sporting): API UTC 2000-09-19 22:00 → local 2000-09-20 (report date used).

## 3. Goals (144)
- TM report goals minus own goals: 2000-05-20 Unterhaching 20' and 2003-05-10 Hertha 5' (both own_goal=1; API excludes them too).
- PK goals 17 per TM report penalty flag (list in NOTE).
- Self-assist rows (2005-03-19 87' pen, 2005-04-06 90+3 pen, 2006-12-17 49' free kick, 2008-01-01 60' pen): goal kept, no assist (API assists also 0).
- 2010-08-19 Tavriya 90+2 pen: TM lists Kießling as assist (empty type). A penalty goal has no assist → treated as penalty won by Kießling; irrelevant for Ballack's rows (his PK goal stays). FotMob: no assist.
- FotMob (2010-11 on): 4 of 5 goals match (2 minute diffs 90+2 vs FotMob 90 → TM minute, Klose/Müller precedent). 2011-02-24 Metalist 70' rests on TM (FotMob "Data not found").
- **Score fixes**:
  - 990077 (2000-09-20 Leverkusen 3-2 Sporting): report sequence one goal behind for Leverkusen (list ends 2-2 although final 3:2, HT 0:1). Reconstructed: 12' 0-1, 65' 1-1, 72' 2-1, 77' Neuville 3-1 (Ballack assist, before 2-1), 79' 3-2. Confirmed by DFB datencenter ("2:1 Brdaric 72., 3:1 Neuville 77., 3:2 Sá Pinto 79. pen") via WebSearch.
  - 21622 (2005-05-07 Mainz 2-4 Bayern): report gives Auer 17' and Makaay 17' both "1-1". Statmuse lists Auer 35', Makaay 17'; worldfootball (search summary) credits Ballack's assist. → Makaay 17' (Ballack assist) before 0-0; Ballack 42' before 1-1 (unchanged). HT 1:2 consistent.
- ET: 2007-04-15 FA Cup SF 109' goal (minute > 95 → ET). No 91–95 ET goals needing the flag.

## 4. Assists (75)
Rule: pre-2014-08 TM report assists minus exclusions (Klose/Insigne precedent). 92 TM report assists to others (= API) → 75:
- − 8 penalty won: 6 typed 'Penalty: Fouled player' (2001-09-08, 2002-04-06, 2002-11-06, 2004-05-22, 2008-04-30, 2008-09-24) + 2 **untyped assists on penalty goals** (1999-12-04 Bremen 47' Kirsten pen, 2001-01-28 Stuttgart 66' Kirsten pen) — a penalty goal cannot have a real assist.
- − 8 'Shot on goal': 2001-12-08 85', 2002-10-19 73', 2004-03-13 9', 2004-05-01 40', 2005-04-12 65', 2006-09-09 6', 2007-03-11 22', 2008-10-05 44'.
- − 1 assist to opponent own goal: 2001-10-27 1860 Munich 33' (Hoffmann OG).
- **31 untyped TM assists kept** (17 before 2003-07, 14 in 2003–2010). Reports before ~2003 carry no type, so penalty-won/rebound screening is impossible there; same treatment as Klose's 29 blank-type assists. None re-checked against a second source (Wikipedia has no assists; FotMob has no pre-2010 events; worldfootball/fbref not reachable).
- 2010-12 assists: Valencia 2011-10-19 56' and 2011-11-01 31' confirmed by FotMob. 2011-03-20 Schalke 19' Derdiyok (FotMob Data not found) and 2011-10-15 Gladbach 20' Reinartz (TM 'Header', FotMob none) kept on TM (pre-2014-08 rule) — single-source, noted.
- FotMob season totals: 2008-09 PL FotMob 0 assists vs TM 5 (FotMob season data unreliable that far back; TM rule kept).

## 5. Cross-player consistency (no other files edited)
Checked every same-match row in lam/dro/rob/klo/reu/bal/roo data (minute, score-before, comp, Elo, tie):
- All Lampard/Drogba rows naming Ballack match a Ballack row exactly (2006-10-21, 10-28, 11-08, 11-29, 2007-04-15, 2008-03-01, 03-05 ×2, 04-08, 04-26, 05-05, 2009-02-28, 08-29, 09-20, 2010-01-27, 02-13, 04-17). Ties identical (Olympiacos [2,1,0,0,1,1], Fenerbahce [2,1,1,2,1,1], Porto [2,1,1,1,1,1] with Robben).
- Score timelines consistent with Klose (KL/Werder vs Leverkusen/Bayern: 2002-03-30, 2003-05-31, 2003-10-25, 2004-10-02), Robben/Drogba/Lampard (Chelsea games incl. 2005-04-06 CL vs Chelsea), Bale 2010-04-17, Rooney 2008-04-26, Reus 2011-10-15.
- **Mismatch to flag**: lam.js 2007-03-11 Tottenham (FA Cup QF) 22' Lampard goal has note "Michael Ballack" (assister), but the TM report type is 'Shot on goal', so Ballack's file does not count it as an assist. Lampard's own goal value is unaffected (note text only). Not changed.
- Same-match Elo reuse: 34 rows (Lampard/Drogba/Robben).

## 6. Opponent Elo
Priority: same match in other players' data (34) → team×season table (99) → rank + league model (77) → direct estimates (9).
- Bundesliga 1998-99..2006-07: 2025-26 rank values (base); 2007-08..2009-10 base − season shift (Klose values); 2010-11/2011-12 complete existing rank tables.
- 2. Bundesliga rank values from existing data (1st 1697, 6th 1609); 7th Aue 2005-06 = 1600 (추정, between 6th/8th).
- Other rank values from existing data: Udinese 1999-00 8th of 18 → 1743 (Serie A 18-team value in 2002-03/2003-04 data); Real Madrid 2000-01 1st → 1996 and Barcelona 2001-02 4th → 1811 (La Liga season = 2003-04 values +31 / +16, derived from that season's existing ranks); Sporting 2000-01 3rd → 1716 (Portuguese 3rd in existing data); Ajax 2004-05 2nd → 1735 (Eredivisie constant).
- Estimates (lv "(추정)"): German 3rd-tier Regionalliga flat 1450 (Klose precedent) for all Chemnitz 1996-97 RNO opponents, KL II 1997, Werder II 2002; 4th tier Neunkirchen 2003 1300 (Klose Paloma); Red Star 2001-02 1500; Fenerbahçe 2001-02 1772 (same as other data 2004-06); Maccabi Tel Aviv 2004-05 8th 1400; Tavriya 2010-11 1440 (Vorskla 1440/Karpaty 1450 level); Metalist 2010-11 3rd 1560.
- `elo_table.js` in scratch copy: 0 conflicts.

## 7. Competitions / ties
- DFB-Pokal, FA Cup, League Cup: dc/dk/dsf/df. FA Cup 3rd–5th rounds + replays dc; 6th round + replay ("6th round deciders") dk; replays single (ko 1, Lampard precedent 2009-01-14). League Cup 3rd/4th round dc, 5th (QF) dk, SF two-legged dsf with tie (ag 1, et 1; ≤2017-18).
- DFB-Ligapokal (Klose): first match ('intermediate stage', 2001-07-12) dk; semi dsf; final df; ko 1. Community Shield df.
- CL: 2001-02 second group stage (Group 4/D) clg; clq/cl16/clk/clsf/clf. UEFA Cup 1999-2000 3rd round elk; EL 2010-11 R32 ('Second Round') and last 16 elk; EL play-off (Tavriya) elq.
- Ties: other-leg score from report `other_leg_score`, which is printed as <this leg's home>:<this leg's away>. First legs Ballack did not play: 2001-08-08 Red Star 0:0, 2011-02-17 Metalist 0:4 (Leverkusen won 4-0 away).
- 2003-07-22 Ligapokal semi HSV: 3-3, lost on pens (TM 120 min; sources unclear whether ET was played — no effect, the 90' goal is a single-match ko row).

## 8. Seasons / clubs
Keys chmbk, fckbk, levbk (both spells, Immobile torim precedent), baybk, chebk (unused in index.html). Boundaries 1997-07-01 / 1999-07-01 / 2002-07-01 / 2006-07-01 / 2010-07-01.
July-10 rule for fckbk, levbk, baybk (Klose fckkl/baykl, Ribéry/Müller Bayern): needed for 2000-07-29 and 2001-07-12 Ligapokal, 2001-07-28 BL opener, 2003-07-22, 2004-07-28, 2011-07-30 DFB-Pokal → new season. chmbk, chebk default Aug 1 (Lampard chelm).

## 9. Honours (hon)
TM titles: LG 97/98 KL, 02/03 04/05 05/06 Bayern, 09/10 Chelsea; DC 02/03 04/05 05/06 Bayern + FA Cup 2007/2009/2010; LC 2007 Chelsea, 2005 Bayern (TM label for 2004-08-02 Ligapokal final); SC 09/10 Chelsea; FOY 2002 Leverkusen, 2003 & 2005 Bayern. Runner-up (TM has none): UCL 01/02 Leverkusen, 07/08 Chelsea (Klose precedent: only UCL finals; Lampard additionally lists League Cup 07/08 runner-up — not added here, orchestrator may decide). Saxony Cup excluded.

## 10. Notes
- Position CM (Lampard precedent), flag DE (exists), retired 2012.
- Tool note: running `tools/add_players.py` from the wrong cwd once patched the real src/index.html and hon.js; reverted immediately with `git checkout` (they were clean before).
