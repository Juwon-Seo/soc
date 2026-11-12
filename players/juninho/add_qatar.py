#!/usr/bin/env python3
"""주니뉴 알가라파 카타르 국내 경기 추가 (v1.154, 사용자 결정 'B': 출전이 확인된 24경기)

build_juninho.py 결과에 v1.152 통합 단계의 팀×시즌 Elo 맞춤(--apply)이 덧입혀져 있어
build를 다시 돌리지 않고, 저장소의 src/data/jun.js 에 카타르 경기만 덧붙인다(한 번만 실행).

근거: raw/qatar/ (카타르축구협회 경기 페이지 qfa.qa/en/match-detail/<id> = 날짜·상대·전후반 스코어·득점자 순서,
신문 기사 = 골 시각·출전 확인; README.md 참고)
  python3 players/juninho/add_qatar.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
JS = os.path.join(ROOT, "src", "data", "jun.js")

def half_up(x): return int(x + 0.5)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

# 카타르 스타스리그 최종 순위(영어 위키백과 순위표 = RSSSF; 협회 경기 기록의 알가라파 승무패·득실과 같음)
RANK = {
    "2009-10": ["Al-Gharafa", "Al-Sadd SC", "Al-Arabi SC", "Qatar SC", "Al-Rayyan SC", "Al-Kharaitiyat SC", "Umm Salal SC",
                "Al-Wakrah SC", "Al-Khor SC", "Al-Ahli SC", "Al-Sailiya SC", "Al-Shamal SC"],
    "2010-11": ["Al-Duhail SC", "Al-Gharafa", "Al-Rayyan SC", "Al-Arabi SC", "Qatar SC", "Al-Sadd SC", "Al-Wakrah SC",
                "Al-Kharaitiyat SC", "Umm Salal SC", "Al-Khor SC", "Al-Sailiya SC", "Al-Ahli SC"],
}
def elo(team, season):
    if team == "Al-Markhiya SC":
        return 1300, f"카타르 2부 {season} (추정, 카타르 1부 평균 1460 − 독일 1·2부 평균 차)"
    r = RANK[season].index(team) + 1
    extra = ", 당시 이름 레크위야" if team == "Al-Duhail SC" else ""
    return half_up(1460 + 45 * curve(r, 12)), f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준{extra})"

# 경기: [날짜, 상대, 대회, ko, 시즌, 골 목록[(분, 표기, 골 전 우리, 골 전 상대)]]
# 골 시각을 찾지 못한 골은 협회 하프타임 스코어로 정한 그 반(전반/후반) 안에서 골 순서대로 나눈 분(추정):
# 그 반의 골 n개 중 k번째 → 반 시작 + 45×k/(n+1)
G = [
    ["2009-08-22", "Al-Wakrah SC", "dc", 0, "2009-10", [(75, 0, 2, 2)]],
    ["2009-08-25", "Al-Markhiya SC", "dc", 0, "2009-10", [(38, 0, 4, 0), (79, 0, 7, 0)]],
    ["2009-10-05", "Al-Sailiya SC", "lg", 0, "2009-10", [(95, "90+5", 0, 0)]],
    ["2009-10-09", "Al-Kharaitiyat SC", "dc", 0, "2009-10", [(75, 0, 2, 0)]],
    ["2009-10-24", "Qatar SC", "lg", 0, "2009-10", [(49, "45+4", 1, 2)]],
    ["2009-11-30", "Al-Wakrah SC", "lg", 0, "2009-10", []],
    ["2009-12-21", "Al-Ahli SC", "lg", 0, "2009-10", [(23, 0, 1, 0)]],
    ["2010-01-16", "Al-Shamal SC", "lg", 0, "2009-10", [(62, 0, 2, 1)]],
    ["2010-03-13", "Al-Wakrah SC", "lg", 0, "2009-10", [(56, 0, 2, 0), (79, 0, 3, 1)]],
    ["2010-08-28", "Al-Rayyan SC", "dc", 0, "2010-11", [(83, 0, 5, 1)]],
    ["2010-10-15", "Al-Rayyan SC", "lg", 0, "2010-11", [(30, 0, 0, 1)]],
    ["2010-11-01", "Al-Sailiya SC", "lg", 0, "2010-11", [(15, 0, 0, 0)]],
    ["2010-11-12", "Al-Wakrah SC", "lg", 0, "2010-11", [(34, 0, 2, 0)]],
    ["2010-11-14", "Al-Ahli SC", "lg", 0, "2010-11", [(88, 0, 6, 1)]],
    ["2011-02-11", "Al-Duhail SC", "lg", 0, "2010-11", []],
    ["2011-02-18", "Al-Arabi SC", "lg", 0, "2010-11", [(45, 0, 0, 1)]],
    ["2011-03-11", "Al-Rayyan SC", "lg", 0, "2010-11", [(11, 0, 0, 0)]],
    ["2011-04-10", "Al-Sadd SC", "lg", 0, "2010-11", [(34, 0, 2, 0)]],
    ["2011-04-15", "Al-Wakrah SC", "lg", 0, "2010-11", [(64, 0, 0, 2)]],
    ["2011-04-25", "Al-Rayyan SC", "dsf", 1, "2010-11", [(77, 0, 0, 0)]],
    ["2011-04-29", "Al-Arabi SC", "df", 1, "2010-11", [(76, 0, 1, 0)]],
    ["2011-05-07", "Al-Sadd SC", "dk", 1, "2010-11", [(40, 0, 0, 1)]],
    ["2011-05-16", "Al-Duhail SC", "dsf", 1, "2010-11", []],
    ["2011-05-21", "Al-Rayyan SC", "df", 1, "2010-11", []],
]

t = open(JS, encoding="utf-8").read()
m_e = re.search(r"const JUN_E=(\[.*?\]);\n", t); m_m = re.search(r"const JUN_M=(\[.*?\]);\n", t); m_n = re.search(r"const JUN_NOTE=(\".*\");", t)
E, M, N = json.loads(m_e.group(1)), json.loads(m_m.group(1)), json.loads(m_n.group(1)).split("\n")
if any(m[0] == "2009-08-22" for m in M): sys.exit("이미 추가됨")
for d, o, c, ko, s, goals in G:
    assert not any(m[0] == d for m in M), d
    M.append([d, o, c, 90, 1])
    e, lv = elo(o, s)
    for mi, dm, gf, ga in goals:
        E.append(["g", o, e, c, mi, gf, ga, ko, 0, d, 0, dm, lv, 0])
M.sort(key=lambda r: r[0])
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
MIN_TOT = sum(m[3] for m in M)

def rep(i, old, new):
    assert N[i].count(old) == 1, (i, old)
    N[i] = N[i].replace(old, new)
rep(0, "657경기", f"{NG}경기"); rep(0, "155골", f"{NGo}골")
rep(1, "알가라파 11·0·2", "알가라파 35·22·2"); rep(1, "52,157분", f"{MIN_TOT:,}분")
rep(3, "알가라파 55경기 22골(카타르 스타스리그 40경기 15골, 에미르컵·왕세자컵·셰이크 자심컵 등 컵 15경기 7골; Transfermarkt는 AFC 챔피언스리그 11경기만 있음)이 빠져 있어",
    "알가라파 국내 경기 약 31경기(출전 여부를 확인하지 못한 경기, 아래 '카타르 국내 경기' 참고)가 빠져 있어")
rep(6, "는 90분으로 추정함.", "는 90분으로 추정함(카타르 국내 24경기도 90분 추정, 아래).")
rep(7, "날짜: 리옹·알가라파는 Transfermarkt 날짜(현지).", "날짜: 리옹·알가라파는 Transfermarkt 날짜(현지), 카타르 국내 경기는 카타르축구협회 날짜(현지).")
rep(8, "(기록 286개:", f"(기록 {len(E)}개: 카타르 국내 경기 24, ")
rep(13, "2011.5.5 전 알가라파", "2011.6.1 전 알가라파(카타르 국내 마지막 경기 2011.5.21 에미르컵 결승)")
rep(13, "경계 불일치 0)", "경계 불일치 0)")
QAT = ("카타르 국내 경기: Transfermarkt에는 알가라파 시기 AFC 챔피언스리그 11경기만 있어, 카타르축구협회 공식 사이트 경기 페이지"
       "(날짜·상대·홈/원정·전후반 스코어·득점자 순서, 2009.8~2011.5 알가라파 1군 국내 72경기 전부; 주니뉴는 'REIS Antonio')로 골을 넣었거나 뛴 것이 기사로 확인된 24경기 22골을 넣음 "
       "— 스타스리그 15경기 14골(2009-10 6경기 6골·2010-11 9경기 8골), 셰이크 자심컵 3경기 4골, 스타스컵 1경기 1골, 왕세자컵 2011 준결승·결승 2경기 2골, 에미르컵 2011 8강·준결승·결승 3경기 1골. "
       "협회 리그 기록 합계(2009-10 16승 5무 1패 55득점 16실점, 2010-11 14승 1무 7패 51-31)는 영어 위키백과 순위표와 같고, 22골은 영어 위키백과 알가라파 통산 골 수와 같음(위키백과 리그 15골·협회 14골 차이는 풀지 못함). "
       "골 없이 뛴 4경기는 기사로 확인: 2009.11.30 와크라전(알이티하드, 후반 출전), 2011.2.11 레크위야전(취소된 골), 2011.5.16 에미르컵 준결승·5.21 결승(걸프 타임스). "
       "2009.9.12 코르전·2011.3.6 코르전은 결장 기사가 있어 빼고, 나머지 46경기는 출전 여부 자료가 없어 뺌(위키백과 통산 66경기 기준 약 31경기가 빠짐)")
QAT2 = ("카타르 국내 경기의 추정: 선발·교체와 출전 분 자료가 한 경기도 없어 24경기 모두 90분으로 추정(왕세자컵 준결승·에미르컵 준결승은 120분 경기였으나 90분으로 둠). "
        "도움은 출처가 없어 0, PK 여부를 적은 출처가 없어 22골 모두 PK가 아닌 골로 셈. 골 시각은 8골만 기사로 확인: 2009.10.5 사일리야전 90+5분(알바얀), 2009.10.24 카타르 SC전 45+4분(쿠우라), "
        "2010.1.16 샤말전 62분(알바얀 골 시각 목록 + 협회 득점 순서), 2010.10.15 라이얀전 30분(걸프 타임스 기사 재게재), 2010.11.14 아흘리전 88분(AFP), 2011.2.18 아라비전 45분(알이티하드), "
        "왕세자컵 결승 76분(걸프 타임스·영어 위키백과), 에미르컵 8강 사드전 40분(걸프 타임스 '전반 끝나기 5분 전'). 왕세자컵 준결승 라이얀전은 영어 위키백과 77분을 씀(협회 하프타임 스코어 1-0과 맞지 않음, 골 전 스코어 0-0은 같음). "
        "나머지 14골은 협회 하프타임 스코어로 전반·후반을 정하고, 그 반 안에서 골 순서대로 고르게 나눈 분(예: 후반 골 3개 중 첫째 56분)으로 추정. 골 전 스코어는 모두 협회 득점 순서 기준. "
        "에미르컵 결승 1-1 골은 협회가 주니뉴 골로 적었으나 걸프 타임스가 주니뉴 코너킥에서 나온 조용형 자책골로 적어 넣지 않음(상대 자책골은 도움 아님). "
        "날짜는 협회 기준이며 왕세자컵 결승은 협회 4.24가 아닌 4.29(걸프 타임스·영어 위키백과), 준결승은 4.25(영어 위키백과). "
        "상대 Elo는 마레즈·에투·라울 자료와 같은 카타르 리그 모형(평균 1460·흩어짐 45 × 순위 곡선, 추정)에 그 시즌 최종 순위를 넣고, 2부 알마르키야는 1300(라울 자료 2부와 같은 방식). "
        "대회 비중: 셰이크 자심컵·스타스컵 조별은 국내컵 리그식(라울 선례), 왕세자컵 준결승·결승과 에미르컵 8강·준결승·결승은 국내컵 단판 토너먼트")
N.insert(4, QAT); N.insert(5, QAT2)
NOTE = "\n".join(N)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(JS, "w", encoding="utf-8").write(f"const JUN_E={J(E)};\nconst JUN_M={J(M)};\nconst JUN_NOTE={J(NOTE)};\n")
print(NG, NGo, NA, MIN_TOT, len(E))
