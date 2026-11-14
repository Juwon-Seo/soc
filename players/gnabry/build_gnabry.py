#!/usr/bin/env python3
"""Serge Gnabry: raw/ -> gnabry.json + src/data/gna.js (판정 근거는 judgments.md)

  python3 players/gnabry/build_gnabry.py            # 파일 쓰기
  python3 players/gnabry/build_gnabry.py --debug    # Elo 출처 로그
  python3 players/gnabry/build_gnabry.py --cross    # 동료 자료 대조
  python3 players/gnabry/build_gnabry.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{mul,lew,mus,kan,san,man,rib,rob}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gna.js")
OUT_JSON = os.path.join(HERE, "gnabry.json")
ME = "세르주 그나브리"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 단독 허용(아스널 2014.1.4 1개), 이후 Transfermarkt∩FotMob

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    # PK 유도('Penalty: Fouled player', 득점자 = 동료)
    "2704503|65": "PK 유도(막스 크루제 PK)",
    "2871831|58": "PK 유도(안드레이 크라마리치 PK)",
    "3413099|76": "PK 유도(레반도프스키 PK)",
    "4096246|37": "PK 유도(해리 케인 PK)",
    # 상대 자책골에 준 도움
    "2871793|80": "상대 자책골(길라보기)",
    "3058577|55": "상대 자책골(겐트너)",
    "3135813|39": "상대 자책골(마티프)",
    "3203667|74": "상대 자책골(힌터레거)",
    "3412874|9": "상대 자책골(하우블레이우)",
    "3651086|80": "상대 자책골(에베르통)",
    "3839085|69": "상대 자책골(감보아)",
    # Transfermarkt 단독(FotMob 경기 이벤트 없음) — 서로 독립인 다른 출처 2곳을 찾지 못했거나 리바운드
    "3252165|45": "확인 못 함(토트넘전 레반도프스키 45분: 경기 기사는 문전 혼전 뒤 골로 묘사, 그나브리 패스를 적은 독립 출처 없음; FotMob 선수 경기 목록만 도움 1)",
    "3601588|88": "리바운드(Goal.com 독일어 라이브 티커: 그나브리 슛을 골키퍼 바르가 막은 뒤 톨리소가 흐른 공을 밀어 넣음)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3195536|85": "bundesliga.com 라이브 블로그 'Gnabry … crosses to Goretzka' · worldfootball.net 골 기록 '(Serge Gnabry)'",
    "3515968|17": "Reuters 계열 기사 'drilled in … after Serge Gnabry squared back a Kingsley Coman effort' · Ahram Online 'found unmarked in the box by Serge Gnabry' · laliga.com 문자중계(Opta) 'Assisted by Serge Gnabry' (FotMob 선수 경기 목록도 이 경기 도움 1)",
    "3601588|80": "leinetal24/heidelberg24 라이브 티커(같은 티커 1곳) 'Gnabry … legt … flach in die Mitte zum aufgerückten Cuisance' · 바이에른 구단 경기 기사(스페인어판) 그나브리가 퀴장스를 찾아 줌",
    "3825616|53": "바이에른 구단 경기 기사 '그나브리가 빠져나가 옆으로 내줘 마네가 밀어 넣음' · t-online 라이브 티커 'Sadio Mané, Vorlage Serge Gnabry' (FotMob 선수 경기 목록도 이 경기 도움 1)",
    "4353910|14": "바이에른 구단 경기 기사 '그나브리가 옆으로 내줘 뮐러가 2:0' · bundesliga.com/bulinews 'Serge Gnabry's square pass allowing Müller to slot home' (FotMob 선수 경기 목록도 이 경기 도움 1)",
}
# FotMob 선수 경기 목록에만 도움이 있고 넣지 않은 것: 2025-09-17 첼시전(케인 63분 골, Transfermarkt 'Without assist',
# bundesliga.com은 파블로비치 도움, 여러 기사는 구스토의 패스 실수) — judgments.md

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "GB1"}
CUP = {"DFB", "FAC", "CGB"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid in ("DFL", "USC", "GBCS"): return "df"
    if cid == "CLQ": return "clq"   # 챔스 플레이오프(예선)
    if cid == "KLUB": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2024-25부터 리그 페이즈('Group Stage') 포함
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"   # 녹아웃 플레이오프 = 16강
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"   # 32강(intermediate stage)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파 조별/리그 페이즈, 클럽 월드컵 2025 조별, 튀르키예컵 조별
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if cid in ("CL", "EL", "CLQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CGB":   # 잉글랜드 리그컵 준결승: 2017-18까지 원정 다득점·연장, 2018-19부터 둘 다 없음
        ag = et = int(d < "2018-07-01")
    else:
        sys.exit("합산 규칙 없음 " + cid)
    return [leg, home, fu, ft, ag, et]

# ---------------------------------------------------------------- 이름 정규화·상대 Elo
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"inter milan": "inter"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

with open(os.path.join(ELO, "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != ME]

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 분데스리가 2026-27(진행 중, 11.11 순위): 기존 자료의 2026-27 순위값(2·5·6·9·12·17위 = 1912·1812·1797·1737·1702·1634)이
# 2025-26 순위값과 모두 같아(2025-26 이후 시즌 조정 없음, docs 4절) 2025-26 순위값을 그대로 씀.
BL_2526 = {1: 2006, 2: 1912, 3: 1860, 4: 1828, 5: 1812, 6: 1797, 7: 1777, 8: 1756, 9: 1737, 10: 1723,
           11: 1713, 12: 1702, 13: 1697, 14: 1682, 15: 1661, 16: 1644, 17: 1634, 18: 1613}
# 러시아 프리미어리그 2020-21(16팀): 크바라츠헬리아 자료의 같은 시즌 순위값 2위 1508·5위 1446 사이를 순위로 선형 보간(3위 1487)
RU_2021 = {2: 1508, 3: 1487, 5: 1446}

def model(lg, season, r, n):
    if lg == "L1" and season == "2026-27":
        assert n == 18
        return BL_2526[r], f"분데스리가 {season} (11월 초 현재) {r}위"
    if lg == "RU1" and season == "2020-21" and r in RU_2021:
        return RU_2021[r], f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
    return None
RANK_LG = ["L1", "RU1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL", "KLUB", "USC") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # Transfermarkt 리포트 날짜(유럽 현지), 클럽 월드컵 2025는 미국 현지 날짜로 바꾼 값

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["gnabry_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["gnabry_scorer"] == "1", e["gnabry_assist_other"] == "1"
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

# FotMob에만 있는 도움(넣지 않음) 확인
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local"] if gid in G else "?", ts))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["gnabry_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 없음", gid)); continue
    fg = [r for r in FM_EV[gid] if r["gnabry_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Thomas Müller": ("mul.js", "MUL", "2018-07-01", "2025-07-01"),
         "Robert Lewandowski": ("lew.js", "LEW", "2018-07-01", "2022-07-01"),
         "Jamal Musiala": ("mus.js", "MUS", "2020-06-01", "2099-01-01"),
         "Harry Kane": ("kan.js", "KAN", "2023-08-12", "2099-01-01"),
         "Leroy Sané": ("san.js", "SAN", "2020-07-15", "2025-07-01"),
         "Sadio Mané": ("man.js", "MAN", "2022-07-01", "2023-08-31"),
         "Franck Ribéry": ("rib.js", "RIB", "2018-07-01", "2019-07-01"),
         "Arjen Robben": ("rob.js", "ROB", "2018-07-01", "2019-07-01")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and r[13] == nm:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("그나브리 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] == "Serge Gnabry":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→그나브리 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    # Transfermarkt 그나브리 도움을 이 자료에서 뺀 동료 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["gnabry_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 그나브리 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # 동료 파일에서 그나브리 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
    for e in EVENTS:
        if e["gnabry_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 그나브리 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("arsgn", "2015-08-07", "아스널", "2012~2015"), ("wbagn", "2016-02-01", "웨스트 브로미치 앨비언", "2015"),
         ("arsgn", "2016-08-31", "아스널", "2016"), ("svwgn", "2017-07-01", "베르더 브레멘", "2016~2017"),
         ("hofgn", "2018-07-01", "호펜하임", "2017~2018"), ("baygn", None, "바이에른 뮌헨", "2018~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
CLUB_KO["hofgn"] = "TSG 호펜하임"
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"11": "arsgn", "984": "wbagn", "86": "svwgn", "533": "hofgn", "27": "baygn"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"세르주 그나브리(아스널·웨스트 브로미치 앨비언·베르더 브레멘·TSG 호펜하임·바이에른 뮌헨)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 코번트리 시티전 ~ {d_(M[-1][0])} 도르트문트전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·독일 대표팀·유소년과 2군(아스널 U21·U23·UEFA 유스리그, 웨스트 브롬 U21, 호펜하임 2군 1경기, 슈투트가르트 U17) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 403경기 전부), 골·도움은 FotMob 경기 이벤트와 대조함",
    "경기 수·골은 영어 위키백과 클럽·시즌별 기록과 같음(바이에른 2023-24 챔스만 위키백과 8경기 vs Transfermarkt·FotMob 7경기 — Transfermarkt를 씀). FotMob 경력 합계(403경기 126골)와도 같음",
    "골: Transfermarkt와 FotMob이 모든 경기에서 수·스코어·PK 여부가 같음. PK 골 2개(2016.11.6 샬케전 42분, 2023.2.11 보훔전 73분)는 Transfermarkt 리포트가 그나브리를 도움(PK 유도)으로도 적었지만 본인 골의 본인 도움이라 도움으로 세지 않음",
    f"도움: 2014년 7월까지는 Transfermarkt 도움(2014.1.4 토트넘전 FA컵 31분 카소를라 골 1개, FotMob 경기 이벤트에는 도움 없음), 그 뒤는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것. 도움 {NA} = Transfermarkt 82 − PK 유도 4(2017.2.5 아우크스부르크전 크루제, 2018.3.17 묀헨글라트바흐전 크라마리치, 2021.1.3 마인츠전 레반도프스키, 2024.5.4 슈투트가르트전 케인) − 상대 자책골에 준 도움 7(2018.3.10 볼프스부르크전, 2019.1.27 슈투트가르트전, 2019.3.13 리버풀전, 2020.5.23 프랑크푸르트전, 2021.5.22 아우크스부르크전, 2021.10.20 벤피카전, 2022.8.21 보훔전) − Transfermarkt 단독이고 확인 못 했거나 리바운드인 2",
    "뺀 Transfermarkt 단독 도움 2개: 2019.10.1 토트넘전(챔스 조별) 45분 레반도프스키 골(경기 기사들은 문전 혼전 뒤 골로 적고 그나브리 패스를 적은 독립 출처를 못 찾음), 2021.8.25 브레머 SV전(DFB-포칼) 88분 톨리소 골(독일어 라이브 티커: 그나브리 슛을 골키퍼가 막은 뒤 흐른 공을 톨리소가 밀어 넣음 — 리바운드)",
    "FotMob 경기 이벤트에 없지만 다른 출처 2곳이 그나브리 도움으로 적어 넣은 5개: 2019.8.12 코트부스전(DFB-포칼) 85분 고레츠카 골(bundesliga.com 라이브 블로그·worldfootball.net), 2021.2.8 알아흘리전(클럽 월드컵 준결승) 17분 레반도프스키 골(로이터 계열 기사·Ahram Online, laliga.com 문자중계도 같음), 2021.8.25 브레머 SV전 80분 퀴장스 골(독일 라이브 티커·바이에른 구단 경기 기사), 2022.8.31 빅토리아 쾰른전(DFB-포칼) 53분 마네 골(바이에른 구단 경기 기사·t-online 라이브 티커), 2024.8.16 울름전(DFB-포칼) 14분 뮐러 골(바이에른 구단 경기 기사·bundesliga.com)",
    "FotMob 선수 경기 목록에만 있는 도움 1개(2025.9.17 첼시전 챔스 리그 페이즈, 케인 63분 골)는 넣지 않음: Transfermarkt는 도움 없음, bundesliga.com은 파블로비치 도움, 여러 기사는 상대 구스토의 패스 실수로 적음",
    f"도움 합계 비교: Transfermarkt 82·FotMob 경력 69·이 계산기 {NA}",
    "같은 경기 동료 자료(뮐러·레반도프스키·무시알라·케인·자네·마네·로번)와 그나브리 도움 → 동료 골, 동료 도움 → 그나브리 골의 날짜·분·스코어·대회·상대 Elo가 모두 같음. Transfermarkt가 동료 도움으로 적은 그나브리 골 4개(2018.12.1 브레멘전·2021.8.22 쾰른전 뮐러, 2019.2.6 헤르타전 레반도프스키, 2023.5.6 브레멘전 무시알라)는 FotMob에 도움이 없어 동료 자료에서도 도움으로 세지 않았음(골 기록에는 영향 없음)",
    "출전 분은 Transfermarkt. FotMob 선수 경기 목록과 1분 차이가 흔하고 큰 차이는 2018.3.31 쾰른전(호펜하임) 1경기(Transfermarkt 90분, FotMob 78분)",
    "날짜는 현지 날짜. 클럽 월드컵 2025 보카 주니어스전은 미국 현지 날짜 2025.6.20(Transfermarkt 리포트는 6.21)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(뮐러·레반도프스키·무시알라·케인·자네·마네·로번·리베리 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 순위를 리그 모형에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']})",
    "순위표+모형 2개: 2020.12.9 로코모티프 모스크바전은 러시아 프리미어리그 2020-21 3위(16팀)를 크바라츠헬리아 자료의 같은 시즌 2위(1508)·5위(1446) 값 사이로 보간한 1487(리그 수준 추정; 다른 선수 자료의 2019-20 1640·2021-22 1600 추정값과 차이가 큼), 2026.10.25 프라이부르크전은 분데스리가 2026-27 진행 중 순위(11월 초 3위)에 다른 선수 자료와 같은 순위값 1860",
    "대회 비중: DFB-포칼·FA컵·리그컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), DFL-슈퍼컵·UEFA 슈퍼컵은 국내컵 결승, 클럽 월드컵(2021 카타르·2025 미국)은 클럽 월드컵으로 계산함. 챔스 리그 페이즈(2024-25부터)는 조별과 같고, 녹아웃 플레이오프는 16강, 호펜하임의 2017 챔스 플레이오프(리버풀전)는 챔스 예선으로 계산함. 2020년 8월 챔스 8강·4강·결승은 단판. 클럽 월드컵 2025 조별은 리그식(무승부 1점)",
    f"두 경기 합산(챔스 토너먼트·예선) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지. 그나브리가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 바이에른은 뮐러·무시알라 자료와 같이 7월 10일 기준이되 2020.7.1~9.1(코로나로 늦게 끝난 2019-20 DFB-포칼 결승·챔스)은 2019-20. 아스널·웨스트 브롬·브레멘·호펜하임은 8월 1일 기준. 클럽 구분은 2015.8.7 전 아스널, 2016.2.1 전 웨스트 브롬(임대), 2016.8.31 전 아스널(복귀, 경기 없음), 2017.7.1 전 브레멘, 2018.7.1 전 호펜하임(임대), 이후 바이에른",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2019-20, 분데스리가 우승 7회(2018-19~2022-23·2024-25·2025-26), DFB-포칼 2018-19·2019-20·2025-26, DFL-슈퍼컵 5회, UEFA 슈퍼컵 2020, 클럽 월드컵 2020-21, FA컵 2014·2015와 커뮤니티 실드 2014(아스널, 결승 출전 없음). 올림픽 득점왕(2016)·U-21 유로 우승 등 대표팀 기록은 뺌",
    f"현재 선수(바이에른). 마지막 반영 경기 {d_(M[-1][0])} 도르트문트전(2026.11.11 수집)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "clq", "cwc"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const GNA_E={J(E)};\nconst GNA_M={J(M)};\nconst GNA_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
