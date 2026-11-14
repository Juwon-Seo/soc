#!/usr/bin/env python3
"""라울·스네이더르 카타르 국내 컵 경기 추가(v1.155, 주니뉴 v1.154와 같은 기준: 골을 넣었거나 기사로 출전이 확인된 경기만).

근거: players/raul/raw/qatar/, players/sneijder/raw/qatar/ (카타르축구협회 경기 페이지 = 날짜·전후반 스코어·득점자 순서,
신문 기사 = 골 시각·출전). 저장소의 src/data/rau.js·sne.js 에 직접 덧붙인다(한 번만 실행).
  python3 players/add_qatar_cups.py
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def half_up(x): return int(x + 0.5)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def q(season, r, n, extra=""):
    return half_up(1460 + 45 * curve(r, n)), f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준{extra})"

# 순위: 영어 위키백과 시즌 순위표(RSSSF). 기존 자료에 같은 팀·시즌 값이 있으면 같은 값이 나옴(라이얀 2012-13 1482, 코르 2013-14 1428, 라이얀 2017-18 1493, 아라비 2018-19 1456)
# [날짜, 상대, 대회, ko, Elo, lv, 출전 분, 추정 여부, 골[(분, 골 전 우리, 골 전 상대)]]
RAU = [
    ["2012-08-10", "Al-Arabi SC", "dsf", 1, *q("2012-13", 11, 12), 90, 1, [(30, 1, 0)]],
    ["2013-05-18", "Al-Rayyan SC", "df", 1, *q("2012-13", 4, 12), 90, 1, [(55, 0, 2)]],
    ["2013-07-25", "Al-Kharaitiyat SC", "dc", 0, *q("2013-14", 12, 14), 45, 0, []],
    ["2013-07-29", "Al-Khor SC", "dc", 0, *q("2013-14", 11, 14), 90, 1, [(22, 0, 1)]],
]
SNE = [
    ["2018-04-22", "Al-Duhail SC", "dsf", 1, *q("2017-18", 1, 12), 90, 1, []],
    ["2018-05-12", "Al-Rayyan SC", "dsf", 1, *q("2017-18", 3, 12), 90, 1, []],
    ["2019-01-10", "Al-Arabi SC", "dc", 0, *q("2018-19", 6, 12), 90, 1, [(74, 0, 1)]],
]
assert RAU[1][4] == 1482 and RAU[3][4] == 1428 and SNE[1][4] == 1493 and SNE[2][4] == 1456

def patch(pre, games, notefix):
    fn = os.path.join(ROOT, "src", "data", pre.lower() + ".js")
    t = open(fn, encoding="utf-8").read()
    E = json.loads(re.search(rf"const {pre}_E=(\[.*?\]);\n", t).group(1))
    M = json.loads(re.search(rf"const {pre}_M=(\[.*?\]);\n", t).group(1))
    N = json.loads(re.search(rf"const {pre}_NOTE=(\".*\");", t).group(1)).split("\n")
    for d, o, c, ko, elo, lv, mn, est, goals in games:
        if any(m[0] == d for m in M): sys.exit(f"{pre} {d} 이미 있음")
        M.append([d, o, c, mn, 1] if est else [d, o, c, mn])
        for mi, gf, ga in goals:
            E.append(["g", o, elo, c, mi, gf, ga, ko, 0, d, 0, 0, lv, 0])
    M.sort(key=lambda r: r[0])
    E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
    stats = (len(M), sum(r[0] == "g" for r in E), sum(m[3] for m in M))
    fixes = notefix(stats)
    for i, old, new in fixes:
        if i is None: continue
        assert N[i].count(old) == 1, (pre, i, old)
        N[i] = N[i].replace(old, new)
    for i, old, new in sorted((f for f in fixes if f[0] is None), key=lambda f: -f[2][0]):
        N.insert(new[0], new[1])
    NOTE = "\n".join(N)
    for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1."]:
        if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)
    J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    open(fn, "w", encoding="utf-8").write(f"const {pre}_E={J(E)};\nconst {pre}_M={J(M)};\nconst {pre}_NOTE={J(NOTE)};\n")
    print(pre, stats, len(E))

def rau_fix(s):
    ng, gl, mn = s
    alsad = next(i for i in range(30) if RAU_N[i].startswith("알사드: "))
    return [
        (0, "917경기", f"{ng}경기"), (0, "385골", f"{gl}골"),
        (1, "알사드 46·13·0", "알사드 50·16·0"), (1, "75,100분", f"{mn:,}분"),
        (alsad, "경기 기사로 날짜·상대·출전·골 시각을 확인한 2경기만 넣음:", "경기 기사로 날짜·상대·출전·골 시각을 확인한 2경기를 먼저 넣고(아래), 카타르축구협회 경기 페이지(날짜·전후반 스코어·득점자 순서; 라울은 'BLANCO Raul')와 기사로 4경기를 더 넣음(아래 '알사드 국내 컵 추가'):"),
        (alsad, "나머지 15경기 3골(2012 셰이크 자심컵 4강 알아라비전 3-0 골 등)은 골 시각이나 출전 기록을 찾지 못해 넣지 않음.", "협회 기록의 라울 컵 골은 5개로 위키백과와 같음."),
        (None, None, (alsad + 1,
         "알사드 국내 컵 추가(주니뉴 알가라파 경기와 같은 기준: 골을 넣었거나 기사로 출전이 확인된 경기만): 2012.8.10 셰이크 자심컵 준결승 알아라비전 3-0 승 두 번째 골(골 전 1-0, 협회 하프타임 0-2로 전반 골 — 시각 자료가 없어 전반 골 2개 중 둘째인 30분으로 추정), "
         "2013.5.18 에미르컵 결승 알라이얀전 1-2 패 만회 골(골 전 0-2, 걸프 타임스 55분·페닌슐라 56분 → 55분), 2013.7.25 셰이크 자심컵 조별 알카라이티야트전 2-0 승(골 없음, 걸프 타임스: 주장으로 선발해 전반만 뜀 → 45분), "
         "2013.7.29 셰이크 자심컵 조별 알코르전 1-5 패 동점 골(골 전 0-1, 페닌슐라·QNA 22분; 페닌슐라는 경기일을 화요일(7.30)로 적었으나 협회 날짜 7.29를 씀). 출전 분은 7.25 경기 외에는 자료가 없어 90분 추정, 도움 자료 없음, 네 골 모두 PK 아님(결승 골은 기사로 확인, 나머지는 PK라는 출처가 없음). "
         "알사드 1군 국내 컵 30경기(셰이크 자심컵 10·스타스컵 11·왕세자컵 3·에미르컵 6)를 협회에서 찾았고 위키백과는 라울 17경기로 적으나, 나머지 11경기는 출전을 확인할 자료가 없어 뺌(2012.8.14 셰이크 자심컵 결승은 '알사드 진영에 있었다'는 기사만 있어 뺌). "
         "2013년 7월 셰이크 자심컵 2경기는 8월 1일 시즌 기준으로 2012-13 시즌에 들어감(상대 Elo는 2013-14 순위). 상대 Elo는 카타르 리그 모형에 영어 위키백과 최종 순위(알아라비 2012-13 11위, 알카라이티야트 2013-14 14팀 중 12위). "
         "셰이크 자심컵 준결승·에미르컵 결승은 국내컵 단판, 셰이크 자심컵 조별은 국내컵 리그식. 2012.8.4 알메사이미르전 골(90분 PK)은 협회 기록에서 후반 두 번째 골로 맞음(걸프 타임스에는 시각·PK 언급 없음)")),
    ]

def sne_fix(s):
    ng, gl, mn = s
    return [
        (0, "575경기", f"{ng}경기"), (0, "154골", f"{gl}골"), (0, "~ 2018.12.6 알아흘리전", "~ 2019.1.10 알아라비전"),
        (1, "알가라파 30·18·4", "알가라파 33·19·4"), (1, "43,998분", f"{mn:,}분"),
        (4, "클럽별 경기 수는 영어 위키백과와 같음(통산 575경기;", "클럽별 경기 수는 Transfermarkt 기준으로 영어 위키백과와 같음(통산 575경기, 여기에 아래 카타르 컵 3경기를 더함;"),
        (4, "골은 영어 위키백과(156골)보다 2개 적음", "골은 영어 위키백과(156골)보다 1개 적음"),
        (4, "과 알가라파 2018-19 QSL컵 두 번째 경기 1골(영어 위키백과 QSL컵 2경기 2골, Transfermarkt 1경기 1골; 경기 기사로 찾지 못함)", ". 알가라파 2018-19 QSL컵 두 번째 골(영어 위키백과 QSL컵 2경기 2골, Transfermarkt 1경기 1골)은 아래 카타르 컵 추가로 채움"),
        (None, None, (5,
         "알가라파 카타르 컵 추가(주니뉴 알가라파 경기와 같은 기준: 골을 넣었거나 기사로 출전이 확인된 경기만, Transfermarkt에 없는 경기): 카타르축구협회 경기 페이지(날짜·전후반 스코어·득점자 순서)와 기사로 "
         "2019.1.10 QSL컵 조별 5라운드 알아라비전 1-1 동점 골(골 전 0-1, 페닌슐라 74분 직접 프리킥, PK 아님), 2018.4.22 왕세자컵 준결승 알두하일전 1-6 패(페닌슐라: 슈팅이 막힘), 2018.5.12 에미르컵 준결승 알라이얀전 0-3 패(페닌슐라)를 넣음. "
         "세 경기 출전 분은 자료가 없어 90분 추정, 도움 없음. 2018.10.11 QSL컵 알두하일전은 부상으로 몇 경기 빠졌다는 기사(페닌슐라 10.27)가 있어, 2019.1.31 QSL컵 결승은 '거의 출전 불가'라는 감독 말만 있어, 나머지 컵 경기(QSL컵 8강·준결승, 에미르컵 2019 등)는 출전 자료가 없어 뺌. "
         "상대 Elo는 카타르 리그 모형에 영어 위키백과 최종 순위(알두하일 2017-18 1위, 알라이얀 2017-18 3위, 알아라비 2018-19 6위). 왕세자컵·에미르컵 준결승은 국내컵 단판, QSL컵 조별은 리그식")),
        (20, "마지막 경기 2018.12.6 알아흘리전", "마지막 경기 2019.1.10 QSL컵 알아라비전(Transfermarkt 마지막 경기는 2018.12.6 알아흘리전)"),
    ]

t = open(os.path.join(ROOT, "src/data/rau.js"), encoding="utf-8").read()
RAU_N = json.loads(re.search(r"const RAU_NOTE=(\".*\");", t).group(1)).split("\n")
patch("RAU", RAU, rau_fix)
patch("SNE", SNE, sne_fix)
