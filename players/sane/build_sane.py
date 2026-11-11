#!/usr/bin/env python3
"""Leroy Sané: raw/ -> sane.json + src/data/san.js (판정 근거는 judgments.md)

  python3 players/sane/build_sane.py            # 파일 쓰기
  python3 players/sane/build_sane.py --debug    # Elo 출처 로그
  python3 players/sane/build_sane.py --cross    # 동료 자료 대조
  python3 players/sane/build_sane.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{kdb,agu,ste,mah,bsi,sil,mul,lew,mus,kan,man}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "san.js")
OUT_JSON = os.path.join(HERE, "sane.json")
ME = "르로이 자네"
GAP = "2014-08-01"   # 도움 출처 기준일(이후 Transfermarkt∩FotMob). 자네의 성인 경기 도움은 모두 이후

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
    "2698369|36": "PK 유도(가브리에우 제주스 PK, 'Penalty: Fouled player')",
    "4312021|32": "PK 유도(해리 케인 PK, 'Penalty: Fouled player')",
    "3050184|84": "상대 자책골(콩골로)",
    "3496449|47": "상대 자책골(아체르비)",
    "3911787|66": "상대 자책골(단브로시오)",
    "4373783|90+3": "상대 자책골(마치마, 'Shot on goal')",
    # Transfermarkt 단독(FotMob 경기 이벤트·선수 경기 목록 모두 도움 없음) + 경기 기사로 도움 아님
    "2460896|9": "굴절(Sky Sports: 자네 패스가 하르니크 맞고 굴절, 니더마이어 걷어내기 실패 뒤 훈텔라르 골)",
    "2917415|69": "자네가 태클당한 뒤 흐른 공(맨시티 공식·SI 등: 페르난지뉴 패스 → 자네 돌파 중 알비올 태클 → 아구에로가 흐른 공 슛)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3515968|85": "Malay Mail(AFP) 'headed in a Leroy Sane cross' · Eurosport 'far-post header from substitute Leroy Sane's cross'",
    "3601588|8": "leinetal24 라이브 티커 'nach Vorarbeit von Sané' · beIN Sports 'Sane's cutback' · Mozzart Sport",
    "3601588|28": "Eurosport/TNT 'allowed Leroy Sane to square for Choupo-Moting' · Sofascore 이벤트 · FotMob 선수 경기 목록(이 경기 도움 1)",
    "3825616|82": "fussballtransfers.com 'Assist L. Sané' · kickingdata.com 'Assistant: L. Sané'",
    "4780386|22": "Türkgün·İşçi Haber(같은 통신 기사로 보임) 'Leroy Sane'den pası alan Kutucu'",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "GB1", "TR1"}
CUP = {"DFB", "FAC", "CGB", "TRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid in ("DFL", "USC", "GBCS"): return "df"
    if cid == "TRS":
        return "dsf" if r.startswith("semi") else "df"    # 튀르키예 슈퍼컵 4팀: 준결승 dsf, 결승 df
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
    if cid in ("CL", "EL"):
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

# 쉬페르리그 2025-26 이후(18팀): 리그 평균 1567·흩어짐 119(살라 자료의 튀르키예 회귀) × 순위 곡선.
# 살라 자료에 있는 순위값(1·2·4·10·13·14·17위)은 그대로, 나머지는 같은 곡선(세군다 고정값에서 되살린 21칸 곡선)으로
# 계산하고 살라 값과의 차이를 이웃 순위 사이에서 보간해 맞춤(judgments.md 7절).
TR_18 = {1: 1865, 2: 1755, 3: 1695, 4: 1656, 5: 1633, 6: 1614, 7: 1595, 8: 1570, 9: 1547, 10: 1533,
         11: 1520, 12: 1509, 13: 1502, 14: 1484, 15: 1461, 16: 1445, 17: 1429, 18: 1409}

def model(lg, season, r, n):
    if lg == "TR1" and season == "2025-26":
        assert n == 18
        return TR_18[r], f"쉬페르리그 {season} {r}위"
    return None
RANK_LG = ["TR1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("AC Sparta Praha"), "2015-16"): (1560, "체코 2015-16 2위 (추정, 다른 선수 자료 스파르타 프라하 2014-15 2위 1560과 같음)"),
    (key("Asteras Tripolis"), "2015-16"): (1450, "그리스 2015-16 7위 (추정, 다른 선수 자료 아스테라스 2014-15 1450과 같음)"),
}

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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "KLUB", "USC") else [eu]
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
        if r["sane_assist"] == "1":
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
    isg, isa = e["sane_scorer"] == "1", e["sane_assist_other"] == "1"
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
    if e["sane_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 없음", gid)); continue
    fg = [r for r in FM_EV[gid] if r["sane_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
MATES = {"Kevin De Bruyne": ("kdb.js", "KDB", "2016-08-02", "2020-07-15"),
         "Sergio Agüero": ("agu.js", "AGU", "2016-08-02", "2020-07-15"),
         "Raheem Sterling": ("ste.js", "STE", "2016-08-02", "2020-07-15"),
         "Riyad Mahrez": ("mah.js", "MAH", "2018-07-10", "2020-07-15"),
         "Bernardo Silva": ("bsi.js", "BSI", "2017-07-01", "2020-07-15"),
         "David Silva": ("sil.js", "SIL", "2016-08-02", "2020-07-15"),
         "Thomas Müller": ("mul.js", "MUL", "2020-07-15", "2025-07-01"),
         "Robert Lewandowski": ("lew.js", "LEW", "2020-07-15", "2022-07-01"),
         "Jamal Musiala": ("mus.js", "MUS", "2020-07-15", "2025-07-01"),
         "Harry Kane": ("kan.js", "KAN", "2023-08-12", "2025-07-01"),
         "Sadio Mané": ("man.js", "MAN", "2022-07-01", "2023-08-31")}
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
            CROSS.append(("자네 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] == "Leroy Sané":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→자네 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    # Transfermarkt 자네 도움을 이 자료에서 뺀 동료 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["sane_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 자네 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # 동료 파일에서 자네 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
    for e in EVENTS:
        if e["sane_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 자네 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("s04sa", "2016-08-02", "샬케 04", "2014~2016"), ("mcisa", "2020-07-15", "맨체스터 시티", "2016~2020"),
         ("baysa", "2025-07-01", "바이에른 뮌헨", "2020~2025"), ("galsa", None, "갈라타사라이", "2025~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"33": "s04sa", "281": "mcisa", "27": "baysa", "141": "galsa"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
OPP_KO = {"VfB Stuttgart": "슈투트가르트", "Amed SK": "아메드 SK"}
NOTE_LINES = [
    f"르로이 자네(샬케 04·맨체스터 시티·바이에른 뮌헨·갈라타사라이)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 슈투트가르트전 ~ {d_(M[-1][0])} 아메드 SK전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·독일 대표팀·유소년(샬케 U17·U19, UEFA 유스리그)·맨시티 U23 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 473경기 전부), 골·도움은 FotMob 경기 이벤트와 대조함",
    "경기 수·골은 영어 위키백과 클럽·시즌별 기록과 같음(갈라타사라이 2026-27만 위키백과가 챔스 4경기를 아직 넣지 않아 2경기 적음). FotMob 경력 합계(473경기 120골)와도 같음",
    "골: Transfermarkt와 FotMob이 모든 경기에서 수·스코어·PK 여부가 같음(PK 골 없음). 분은 Transfermarkt 추가시간 표기를 씀",
    f"도움: Transfermarkt와 FotMob 경기 이벤트가 함께 센 것만 씀(자네의 성인 경기는 모두 2014년 8월 이후). 도움 {NA} = Transfermarkt 리포트 116 − PK 유도 2(2017.5.13 레스터전 36분 제주스 PK, 2024.4.9 아스널전 32분 케인 PK) − 상대 자책골에 준 도움 4(2018.8.19 허더즈필드전 84분, 2021.2.23 라치오전 47분, 2022.9.7 인테르전 66분, 2025.4.4 아우크스부르크전 90+3분) − Transfermarkt 단독이고 경기 기사로 도움이 아닌 2",
    "뺀 Transfermarkt 단독 도움 2개: 2015.5.2 슈투트가르트전 9분 훈텔라르 골(Sky Sports: 자네 패스가 하르니크에게 굴절되고 수비 걷어내기 실패 뒤 골), 2017.11.1 나폴리전 69분 아구에로 골(맨시티 공식 경기 기사 등: 자네가 돌파하다 알비올에게 태클당한 뒤 흐른 공을 아구에로가 슛)",
    "FotMob에 없지만 다른 출처 2곳이 자네 도움으로 적어 넣은 5개: 2021.2.8 알아흘리전(클럽 월드컵 준결승) 85분 레반도프스키 헤더(AFP·Eurosport), 2021.8.25 브레머 SV전(DFB-포칼) 8·28분 추포모팅 골(독일 라이브 티커·beIN Sports, Eurosport·Sofascore; FotMob 선수 경기 목록도 이 경기 도움 1), 2022.8.31 빅토리아 쾰른전(DFB-포칼) 82분 고레츠카 골(fussballtransfers·kickingdata), 2025.12.18 바샥셰히르전(튀르키예컵 조별) 22분 쿠투추 골(튀르키예 언론 경기 기사 2곳). FotMob에만 있는 도움은 없음",
    "도움 합계 비교: Transfermarkt 116·FotMob 경력 108·이 계산기 108(FotMob과 같은 수지만 경기 구성은 위처럼 다름)",
    "날짜는 현지 날짜. 클럽 월드컵 2025 보카 주니어스전은 미국 현지 날짜 2025.6.20(Transfermarkt 리포트는 6.21)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(데 브라위너·아구에로·스털링·마레즈·베르나르두 실바·다비드 실바·뮐러·레반도프스키·무시알라·케인·마네 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 모형에 넣은 값, 직접 추정 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "쉬페르리그 2025-26은 살라 자료와 같은 튀르키예 리그 수준(평균 1567)에 Transfermarkt 최종 순위(18팀)를 넣음. 살라 자료에 같은 순위 값이 있으면 그 값(1위 1865·2위 1755·4위 1656·10위 1533·17위 1429), 없는 순위(3·5·6·7·16위)는 같은 곡선에 이웃 순위 값과의 차이를 맞춘 값. 2026-27(진행 중)은 다른 선수 자료의 11월 초 순위 값",
    "직접 추정(모두 '추정'): 스파르타 프라하 2015-16(체코 2위) 1560, 아스테라스 트리폴리스 2015-16(그리스 7위) 1450 — 둘 다 다른 선수 자료의 바로 전 시즌 값과 같게 둠",
    "대회 비중: DFB-포칼·FA컵·리그컵·튀르키예컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; FA컵 6라운드는 8강), DFL-슈퍼컵·커뮤니티 실드·UEFA 슈퍼컵·튀르키예 슈퍼컵 결승은 국내컵 결승, 튀르키예 슈퍼컵(4팀) 준결승은 국내컵 준결승, 클럽 월드컵(2021 카타르·2025 미국)은 클럽 월드컵으로 계산함. 챔스 리그 페이즈(2024-25부터)는 조별과 같고, 녹아웃 플레이오프는 16강, 유로파 32강은 유로파 토너먼트로 계산함. 클럽 월드컵 2025 조별과 튀르키예컵 2025-26 조별은 리그식(무승부 1점)",
    f"두 경기 합산(챔스·유로파 토너먼트, 리그컵 준결승) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지, 리그컵 준결승은 2017-18까지 원정 다득점·연장, 2018-19부터 둘 다 없음. 자네가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 바이에른은 뮐러·무시알라 자료와 같이 7월 10일 기준(2022.7.30 DFL-슈퍼컵 = 2022-23), 샬케·맨시티·갈라타사라이는 8월 1일 기준. 클럽 구분은 2016.8.2 전 샬케, 2020.7.15 전 맨시티, 2025.7.1 전 바이에른, 이후 갈라타사라이",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 리그 우승 7회(프리미어리그 2017-18·2018-19, 분데스리가 2020-21~2022-23·2024-25, 쉬페르리그 2025-26), FA컵 2019, 리그컵 2018·2019, 커뮤니티 실드 2018·2019, DFL-슈퍼컵 2021·2022, UEFA 슈퍼컵 2020, 클럽 월드컵 2020-21. 개인상(잉글랜드 올해의 영플레이어 2018·VDV 신인상 2014-15)은 표 항목이 없어 뺐고 유소년·대표팀 기록도 뺌",
    f"현재 선수(갈라타사라이). 마지막 반영 경기 {d_(M[-1][0])} 아메드 SK전(2026.11.11 수집)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const SAN_E={J(E)};\nconst SAN_M={J(M)};\nconst SAN_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
