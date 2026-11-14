# build_gomis.py 뒤쪽: 동료 대조·클럽 합계·설명(NOTE)·일관성 점검·출력 (build_gomis.py가 exec로 읽음)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"pay.js": ("Dimitri Payet", ("Payet",)), "gou.js": ("Yoann Gourcuff", ("Gourcuff",)), "lac.js": ("Alexandre Lacazette", ("Lacazette",)),
             "mer.js": ("Dries Mertens", ("Mertens",)), "fek.js": ("Nabil Fekir", ("Fekir",))}
def mate_hit(name, toksx): return any(t in str(name) for t in toksx)
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and "Gomis" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (x[5], x[6], x[2], x[12], x[3], x[7], x[14:])
            cross.append(("동료 도움→고미스 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "고미스 골 없음"), x[1:8], hit[0][1:8] if hit else None))
    if b in MATE_NAME:
        nm, tk = MATE_NAME[b]
        for r in E:
            if r[0] == "a" and mate_hit(r[13], tk):
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (r[5], r[6], r[2], r[12], r[3], r[7], r[14:])
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("고미스 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))), r[1:8], hit[0][1:8] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == JP and e["assist_id"] and not e["assist_type"].startswith("Penalty") and e["assist_type"] != "Shot on goal":
            for b, (nm, tk) in MATE_NAME.items():
                if b in OTHERS and mate_hit(e["assist_player"], tk):
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and "Gomis" in str(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2005-01-24", "생테티엔"), ("2005-07-01", "트루아"), ("2009-07-29", "생테티엔"), ("2014-07-01", "리옹"), ("2016-07-29", "스완지 시티"),
         ("2017-07-01", "마르세유"), ("2018-08-23", "갈라타사라이 1기"), ("2022-02-02", "알힐랄"), ("2023-08-08", "갈라타사라이 2기"), ("9999-12-31", "가와사키 프론탈레")]
TMCLUB = {"618": "생테티엔", "1095": "트루아", "1041": "리옹", "2288": "스완지 시티", "244": "마르세유", "141": "갈라타사라이", "1114": "알힐랄", "9598": "가와사키 프론탈레"}
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
for g in games:
    if not club_of(ldate(g)).startswith(TMCLUB[g["club_id"]]): sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict()
for _, n in CLUBS: ST.setdefault(n, [0, 0, 0, 0])
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TM_A_API = sum(int(g["assists"] or 0) for g in games)
RES_N = len(RES_G); RES_GO = sum(int(g["goals"] or 0) for g in RES_G)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
SHOT = "슈팅 리바운드('Shot on goal')"; UNC = "2014.8 이후 Transfermarkt에만 있고 경기 기사로 확인 못 함"
KO = {"FC Lorient": "로리앙", "Rubin Kazan": "루빈 카잔", "Athletic Bilbao": "아틀레틱 빌바오", "Al-Faisaly FC": "알파이살리", "GMG Kastamonuspor": "카스타모누스포르",
      "Tranmere Rovers": "트랜미어", "Clermont Foot 63": "클레르몽", "OGC Nice": "니스", "Olympique Marseille": "마르세유", "FC Nantes": "낭트",
      "Konyaspor": "코냐스포르", "Göztepe": "괴즈테페"}
def jl(reason):
    return ", ".join(f"{d_(j[1])} {KO.get(j[2], j[2])}전 {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man" and "추정" in v[2]}, key=lambda t: t[0])
SAME_N = ELO_SRC["같은 경기 다른 선수 자료"]
ADDED = [(d_(v[1]), KO.get(v[2], v[2]), v[3], v[4], v[6]) for v in post_gap_log if v[6]]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"바페팀비 고미스(생테티엔·트루아·리옹·스완지 시티·마르세유·갈라타사라이·알힐랄·가와사키 프론탈레)의 클럽 공식 경기 {NG}경기({d_(first[0])} 르퓌전 ~ {d_(last[0])} 비셀 고베전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(v)}" for n, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(클럽 공식 경기 785경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "생테티엔 2003-04(리그2, 프로 2부)부터 셈. 트루아 임대(2005.1~6)도 리그2. 리옹 2군(4부 CFA) 2013년 8·9월 " + f"{RES_N}경기 {RES_GO}골은 2군 경기라 뺌. 프랑스 대표 경기는 뺌",
    "알힐랄 2018-19 아랍 클럽 챔피언스컵 6경기 5골(영어·프랑스어 위키백과 시즌 합계에만 있음)은 Transfermarkt·FotMob에 경기 기록이 없고 경기별 득점 시간·출전 시간을 찾지 못해 넣지 않음(위키백과 통산 790경기 358골과의 차이 대부분)",
    "클럽별 경기·골은 영어 위키백과와 같음(생테티엔 165·49 vs 위키 164·49: 2003.12.13 쿠프 드 프랑스 르퓌전 35분 출전은 Transfermarkt·프랑스어 위키백과에 있음). 알힐랄은 위키백과 154경기 116골에서 아랍 클럽 챔피언스컵 6경기 5골을 빼면 같음",
    "은퇴: 마지막 공식 경기는 2024.6.16 J1리그 비셀 고베전(61분). Transfermarkt는 2024.9.24 무소속, 2024.11.10 은퇴",
    f"골 {NGo}개 중 PK {NPK}개. 본인 자책골 2개(2019.10.1 AFC 챔스 알사드전 14분, 2020.8.10 알파테흐전 53분)는 셈하지 않음",
    "2014.1.5 쿠프 드 프랑스 라쉬즈쉬르사르트전(6-1)은 Transfermarkt 리포트 골 목록에 상대 골(41분 PK)이 빠져 있어 FotMob 기록으로 골 직전 스코어를 정함: 6분 골 0-0, 56분 골 2-1, 58분 라카제트 골 도움 3-1(구르퀴프·라카제트 자료와 같음)",
    "2011.12.7 챔스 디나모 자그레브전 48분 골은 Transfermarkt 순서(47분 고날롱 골 뒤, 2-1에서)를 따름. FotMob은 고날롱 골보다 앞에 적었으나 UEFA 기사도 고날롱 47분·고미스 48분",
    "출전 분: 2018.8.5 튀르키예 슈퍼컵 아히사르스포르전은 연장·승부차기까지 뛰어 120분(Transfermarkt; FotMob 90분), 2017.12.9 아히사르스포르전은 68분 퇴장(Transfermarkt·beIN 경기 기록; FotMob 90분)",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움을 쓰고, 그 뒤는 Transfermarkt와 FotMob 경기 기록이 같이 적은 도움을 기준으로 함. Transfermarkt에만 있는 도움 중 그 경기 FotMob 기록에 도움 자료가 아예 없는 것은 경기 기사로 확인되면 넣음",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_API}개(본인 골에 본인을 도움으로 적은 리포트 5건은 이미 빠진 수) − 슈팅 리바운드 {EX[SHOT]}개 − 상대 자책골로 이어진 슈팅 리바운드 {EX['상대 자책골 유도']}개 − 2014.8 이후 Transfermarkt에만 있고 기사로 확인되지 않은 {EX[UNC]}개",
    "슈팅 리바운드로 뺀 도움: " + jl(SHOT) + ". 상대 자책골로 뺀 도움: " + jl("상대 자책골 유도"),
    "2014.8 이후 Transfermarkt에만 있어 뺀 도움: 2019.1.21 킹스컵 알파이살리전 79분 나세르 알다우사리(기사에 도움자 없음), 2022.10.19 튀르키예컵 카스타모누스포르전 27분(공식 기록은 상대 자책골)",
    "2014.8 이후 FotMob 기록에 도움 자료가 없어 경기 기사로 확인해 넣은 도움: " + ", ".join(f"{a} {b}전 {c}분 {d}" for a, b, c, d, e in ADDED),
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(FotMob은 2010년 이전 기록이 없고 2010-11~2013-14 도움 칸이 거의 비어 있음)",
    "날짜는 현지 날짜(Transfermarkt 시각을 클럽 나라 시간으로 바꾼 날짜, 원정 경기도 날짜가 바뀌는 시각은 없음)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(파예·구르퀴프·라카제트·메르턴스 등) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값에 넣음",
    "사우디 프로리그 2018-19~2021-22(16팀)는 다른 선수 자료의 2022-23(16팀) 순위값을 쓰고 빈 순위(7·11·14위)는 이웃 값의 가운데, 1·2·16위는 18팀 순위값을 같은 상대 위치로 옮긴 값(1813·1695·1352). 2019-20 시즌은 코로나로 2020.9.9까지 이어져 2020년 8·9월 사우디 경기도 2019-20 순위를 씀",
    "리그2 상대는 리그2 순위값(1위 1669 ~ 20위 1470, 지냑 자료와 같은 표), J1리그 2024(20팀) 19위는 다른 선수 자료 20팀 시즌 19위 값 1501",
    "순위표에 없거나 하위 리그·외국 리그인 상대는 당시 수준을 추정함('추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED),
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·FA컵·리그컵·튀르키예컵·킹스컵·일왕배는 16강까지·8강·준결승·결승, 트로페 데 샹피옹·튀르키예 슈퍼컵·사우디 슈퍼컵·일본 슈퍼컵은 국내컵 결승, UEFA컵 2008-09 1라운드는 유로파 예선, 3라운드(32강)·16강은 유로파 토너먼트, AFC 챔스는 조별·16강, 8강, 준결승, 결승, 클럽 월드컵 2019는 단판",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회 2020-21까지 원정 다득점·연장(2021-22 유로파 16강 바르셀로나전은 원정 다득점 없음), 튀르키예컵 2017-18 원정 다득점·연장, AFC 챔스 2019 토너먼트 원정 다득점·연장(대회 규정), 2023-24 16강은 원정 다득점 없이 연장. 고미스가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움. AFC 챔스 2021 토너먼트는 단판",
    "시즌은 생테티엔·리옹·갈라타사라이는 7월 10일 기준(2005.7.30 리그1 개막전 = 2005-06, 2012.7.28 트로페 데 샹피옹 = 2012-13, 2017.7 유로파 예선 = 2017-18), 가와사키는 달력 연도, 알힐랄은 8월 1일 기준이되 2020.9월 경기(리그 29·30라운드, AFC 챔스 조별)는 2019-20, 나머지는 8월 1일 기준",
    "우승 기록은 Transfermarkt 업적 페이지 기준",
]
NOTE = "\n".join(l for l in NOTE_LINES if l)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elq", "elk", "lg", "acl", "aclk", "cwc"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    allr = sorted(rs, key=lambda r: r[4])
    for a, b in zip(allr, allr[1:]):
        if (b[5] < a[5] or b[6] < a[6]) and not (a[11] and str(a[11]).startswith("45+")): problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[9] in mm and (mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]): problems.append(("상대/대회 M 불일치", r[9], r[1], r[3], mm[r[9]][1:3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const GMS_E={J(E)};\nconst GMS_M={J(M)};\nconst GMS_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "post_gap_tm_only": post_gap_log, "post_gap_verdicts": POST_GAP, "fm_only_seen": fm_only_seen,
           "fm_goal_diff": fm_goal_diff, "own_goals": own_goals, "reserve_excluded": [[g["date_local"], g["opponent"], g["competitionId"], g["playedMinutes"], g["goals"]] for g in RES_G],
           "minute_fixes": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("FotMob 전용", fm_only_seen)
print("FotMob PK 차이", fm_goal_diff)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
print("대조 요약", collections.Counter((c[0], c[4] if c[0].endswith("골") else "") for c in cross))
