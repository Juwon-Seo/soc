# build_cabella.py 뒤쪽: 동료 대조·클럽·시즌·설명(NOTE)·일관성 점검·출력 (build_cabella.py가 exec로 읽음)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE = {"pay.js": ("Payet", ("Payet",)), "gms.js": ("Gomis", ("Gomis",))}
def is_me(n): return bool(re.search(r"Cabella", str(n)))
def same_vals(a, b): return (a[5], a[6], a[2], a[12], a[3], a[7], a[14:]) == (b[5], b[6], b[2], b[12], b[3], b[7], b[14:])
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and is_me(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2], key=lambda r: (not same_vals(r, x), abs(r[4] - x[4])))
            cross.append(("동료 도움→카벨라 골", b, x[9], x[4], "일치" if hit and same_vals(hit[0], x) else ("값 다름" if hit else "카벨라 골 없음"), x[1:9], hit[0][1:9] if hit else None))
    if b in MATE:
        nm, tk = MATE[b]
        for r in E:
            if r[0] == "a" and any(t in str(r[13]) for t in tk):
                hit = sorted([x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2], key=lambda x: (not same_vals(x, r), abs(x[4] - r[4])))
                cross.append(("카벨라 도움→동료 골", b, r[9], r[4], "일치" if hit and same_vals(hit[0], r) else ("값 다름" if hit else "동료 골 없음"), r[1:9], hit[0][1:9] if hit else None))
        for gid, evs in EVS.items():
            if gid not in G: continue
            d = ldate(G[gid])
            for e in evs:
                if e["scorer_id"] == ME and any(t in e["assist_player"] for t in tk):
                    if not any(x[0] == "a" and x[9] == d and is_me(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움(카벨라 골)이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
                if e["assist_id"] == ME and any(t in e["scorer"] for t in tk):
                    if not any(r[0] == "a" and r[9] == d and abs(r[4] - mins(e["minute"])[0]) <= 2 for r in E):
                        cross.append(("Transfermarkt 카벨라 도움(동료 골)을 뺌", b, d, e["minute"], e["assist_type"]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
_seen = set(); cross = [c for c in cross if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("arlcab", "2011-07-01", "아를아비뇽", "아를아비뇽", "2010~2011"),
         ("mtpcab", "2014-07-13", "몽펠리에", "몽펠리에", "2011~2014"),
         ("ncucab", "2015-08-19", "뉴캐슬 유나이티드", "뉴캐슬", "2014~2015"),
         ("omcab", "2017-08-31", "올랭피크 드 마르세유", "마르세유", "2015~2017"),
         ("stecab", "2019-07-26", "AS 생테티엔", "생테티엔", "2017~2019"),
         ("krcab", "2022-04-06", "크라스노다르", "크라스노다르", "2019~2022"),
         ("mtpcab", "2022-07-10", "몽펠리에", "몽펠리에", "2022"),
         ("lilcab", "2025-07-01", "릴", "릴", "2022~2025"),
         ("olycab", "2026-01-01", "올림피아코스", "올림피아코스", "2025"),
         ("nancab", "2026-09-14", "낭트", "낭트", "2026"),
         ("volcab", None, "볼로스", "볼로스", "2026~")]
TMCLUB = {"11300": "arlcab", "969": "mtpcab", "762": "ncucab", "244": "omcab", "618": "stecab", "16704": "krcab", "1082": "lilcab",
          "683": "olycab", "995": "nancab", "60949": "volcab"}
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def stint(d):
    for i, (k, u, *_) in enumerate(CLUBS):
        if u is None or d < u: return i
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "mtpcab":       # 7월 10일 기준(2012.7.28 트로페 데 샹피옹 = 2012-13)
        s_ = y if d[5:] >= "07-10" else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    if club == "krcab":        # 7월 1일 기준(러시아 리그 7월 개막), 단 2020년 7월(코로나로 미뤄진 2019-20 리그)은 2019-20
        if "2020-07-01" <= d < "2020-08-01": return "2019-20"
        s_ = y if d[5:] >= "07-01" else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    if d.startswith("2020-08"): return "2019-20"
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
for g in GAMES:
    if season_of(ldate(g), club_of(ldate(g))) != season(g): sys.exit("시즌 불일치 " + g["gameId"] + " " + ldate(g))
LBL = []
for i, (k, u, n, sh, y) in enumerate(CLUBS):
    nm = n + (" 1기" if i == 1 else " 2기" if i == 6 else "")
    LBL.append(nm)
ST = collections.OrderedDict((l, [0, 0, 0, 0]) for l in LBL)
for m in M: ST[LBL[stint(m[0])]][0] += 1; ST[LBL[stint(m[0])]][3] += m[3]
for r in E: ST[LBL[stint(r[9])]][1 if r[0] == "g" else 2] += 1
SEAS = collections.Counter(season_of(m[0], club_of(m[0])) for m in M)
SEAS_MIN = collections.Counter()
for m in M: SEAS_MIN[season_of(m[0], club_of(m[0]))] += m[3]
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TM_A = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == ME and e["scorer_id"] != ME)
TM_A_API = sum(int(g["assists"] or 0) for g in GAMES)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
KO = {"Dijon FCO": "디종", "Stade Brestois 29": "브레스트", "Stade Rennais FC": "렌", "Olympique Marseille": "마르세유", "Angers SCO": "앙제",
      "PAOK Thessaloniki": "PAOK", "FC Leningradets": "레닌그라데츠", "KÍ Klaksvík": "클락스비크", "Montpellier HSC": "몽펠리에", "Ellas Syros": "엘라스 시로스"}
SCO = {"Olivier Giroud": "지루", "Geoffrey Dernis": "데르니", "Benoît Costil": "코스틸(렌 골키퍼 자책골)", "Morgan Sanson": "상송", "Vincent Manceau": "망소(앙제 자책골)",
       "Viktor Claesson": "클라에손", "Grzegorz Krychowiak": "크리호비아크", "Yusuf Yazıcı": "야즈즈", "Edon Zhegrova": "제그로바", "Jonathan David": "데이비드"}
def jl(reason):
    return ", ".join(f"{d_(j[1])} {KO.get(j[2], j[2])}전 {j[3]}분 {SCO.get(j[4], j[4])}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
FMG = [(gid, e) for gid, evs in EVS.items() if gid in G and gid in FME for e in evs if e["scorer_id"] == ME and e["own_goal"] != "1"]
FM_DIFF = []
for gid, e in FMG:
    f = fm_ev(gid, e["score_home_away_after"])
    if not f or f["cabella_scorer"] != "1": FM_DIFF.append((gid, ldate(G[gid]), e["minute"], "FotMob에 같은 스코어 카벨라 골 없음")); continue
    fmin = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(fmin - mins(e["minute"])[0]) > 1: FM_DIFF.append((gid, ldate(G[gid]), e["minute"], f"FotMob {f['time']}" + (f"+{f['overloadTime']}" if f["overloadTime"] else "")))
    if ("pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower()) != (e["goal_desc"] == "Penalty"): FM_DIFF.append((gid, ldate(G[gid]), e["minute"], "PK 표시 다름"))
FM_N_G = len(FMG); FM_N_GAMES = len({gid for gid, e in FMG})
NO_FM_G = sum(int(g["goals"] or 0) for gid, g in G.items() if gid not in FME)

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
st_txt = ", ".join(f"{n} {c3(v)}" for n, v in ST.items())
SHOT = "슈팅 리바운드('Shot on goal')"
NOTE_LINES = [
    f"레미 카벨라(아를아비뇽·몽펠리에·뉴캐슬·마르세유·생테티엔·크라스노다르·릴·올림피아코스·낭트·볼로스)의 클럽 공식 경기 {NG}경기({d_(first[0])} 낭시전 ~ {d_(last[0])} 아트로미토스전)에서 나온 {NGo}골 {NA}도움, 친선경기·프랑스 대표팀(A·U-21)·몽펠리에 2군·유소년 경기 제외",
    f"클럽별 경기·골·도움: {st_txt}. 출전 분 합계 {MIN_TOT:,}분",
    "현역(볼로스, 그리스 1부): 2026.11.2 아트로미토스전까지 반영(2026.11.7 키피시아전은 벤치, 출전 없음)",
    "몽펠리에 유스 출신. 2009-10 몽펠리에 1군에 올랐지만 무릎 십자인대 부상으로 출전 없음. 2009.5.9 쿠프 강바르델라(유소년컵) 결승 1골과 몽펠리에 2군(프랑스 4부 아마추어) 경기는 넣지 않음. 마르세유(2015-16 임대 뒤 2016년 완전 이적)와 생테티엔(2017-18 임대 뒤 2018년 완전 이적)은 한 클럽으로 셈. 올림피아코스에서 2026.1.1 낭트로 임대된 뒤 2026.7.1 복귀했으나 출전 없이 2026.9.14 볼로스로 이적",
    "소속 팀 리그: 리그1(프랑스)·프리미어리그(잉글랜드)·러시아 프리미어리그·그리스 슈퍼리그 모두 프로 1부",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(클럽 공식 경기 {NG}경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음. 클럽별 경기·골 수는 Transfermarkt·FotMob·프랑스어 위키백과와 같음(영어 위키백과는 생테티엔 2017-18 리그컵 1경기를 더 세고 낭트 리그를 11경기로 적음, 볼로스는 위키백과에 아직 없음)",
    f"골 {NGo}개 중 PK {NPK}개(Transfermarkt 골 유형 'Penalty', 선수 경기 성적 PK 골 수와 경기마다 같음). 자책골 없음. FotMob 경기 기록과 대조함: FotMob에 없는 골 4개(2011.3.12 로리앙전 80분, 2011.5.29 소쇼전 28분, 2012.1.8 프리레메지에르전(쿠프 드 프랑스) 17·40분)는 Transfermarkt·위키백과·FotMob 선수 통산 합계가 모두 이 골을 세고, 로리앙전은 Foot Mercato 경기 기록(80분 카벨라, 케르모르강 도움), 프리레메지에르전은 Eurosport 경기 기록(카벨라 18·41분)으로 확인해 넣음(분은 Transfermarkt). 2014.2.22 아작시오전 골은 Transfermarkt 90+4분·FotMob 90분 → Transfermarkt",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움(단일 출처 허용), 그 뒤는 Transfermarkt와 FotMob 경기 기록이 같이 적은 도움을 기준으로 하고, 한쪽에만 있는 도움은 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 슈팅 리바운드 {EX[SHOT]}개 − 2014.8 이후 Transfermarkt에만 있고 다른 출처 2곳으로 확인되지 않은 {EX['2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)']}개(Transfermarkt 선수 경기 성적 도움 {TM_A_API}개와 리포트 도움 수가 같음)",
    "PK 유도로 뺀 도움: " + jl("PK 유도") + ". 상대 자책골 유도로 뺀 도움: " + jl("상대 자책골 유도") + ". 슈팅 리바운드로 뺀 도움: " + jl(SHOT),
    "Transfermarkt에만 있어 뺀 도움: " + jl("2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)") + "(FotMob 경기 기록에 도움자 칸이 비어 있고 경기 기사에서 확인 못 함). Transfermarkt에만 있지만 넣은 도움: 2018.1.7 님전(쿠프 드 프랑스) 63분 베리치(Objectif Gard 경기 기사·Sporting Life 문자 중계: 카벨라 프리킥에 베리치 헤딩), 2026.1.11 니스전(쿠프 드 프랑스) 52분 기라시(Sky Sports 문자 중계·PlayerStats 경기 기록)",
    "FotMob에만 있어 뺀 도움: 2018.12.5 보르도전 67분 카즈리(Transfermarkt는 도움자 없음, 다른 기록 사이트 1곳만 카벨라 도움). 같은 경기 16분 골은 Transfermarkt가 디오니, FotMob이 카즈리 골로 적었지만 둘 다 카벨라 도움이라 넣음(득점자는 Transfermarkt)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(FotMob은 2010-11~2013-14 도움 칸이 거의 비어 있음)",
    "날짜는 경기 현지 날짜(Transfermarkt 일정·리포트 날짜, 모두 유럽 경기). 출전 분은 Transfermarkt 그대로(연장 경기는 연장 포함). 2024.12.11 슈투름 그라츠전 Transfermarkt 리포트는 3·4번째 골 스코어 순서가 바뀌어 있어 FotMob 순서로 셈(카벨라 기록 없음)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(파예·고미스) 값을 먼저 쓰고({ELO_SRC['같은 경기 다른 선수 자료']}개 기록), 없으면 직접 추정({ELO_SRC['직접 추정']}개), 기존 선수 자료의 같은 팀·같은 시즌 값({ELO_SRC['기존 팀×시즌 값']}개), 그다음 그 시즌 최종 순위를 리그 모형에 넣은 값({ELO_SRC['순위표+리그 모형']}개)",
    "리그 수준: 리그2(프랑스 2부)는 기존 순위값이 없는 시즌이라 평균 1540·2부 흩어짐 모형(투르 2011-12 6위·부르앙브레스 2015-16 11위·님 2017-18 2위). 러시아 프리미어리그 2019-20은 기존 자료 순위값에 맞는 평균 약 1430 모형, 2020-21·2021-22는 기존 자료 순위값 사이를 앞뒤 값으로 나누고(빈 순위 1칸은 가운데) 끝 순위는 가까운 순위값에 순위 곡선 차이(흩어짐 63)를 더함. 그리스 슈퍼리그는 발부에나 자료 모형(국가 계수 회귀), 2025-26은 국가 계수가 확정되지 않아 2024-25 리그 수준을 씀. 그리스 순위는 플레이오프·플레이아웃 뒤 공식 최종 순위(PAOK 2020-21 2위, 판세라이코스 2025-26 14위; Transfermarkt 표는 정규 시즌 순서)",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED),
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·FA컵·잉글랜드 리그컵·러시아컵·그리스컵은 16강까지·8강·준결승·결승, 트로페 데 샹피옹은 국내컵 결승 비중. 러시아컵 2021-22 조별·그리스컵 2025-26 리그 단계는 리그식 단판. 챔스 2024-25 리그 단계는 챔스 리그·조별, 유로파 32강('intermediate stage')은 유로파 토너먼트, 컨퍼런스리그 조별·16강·8강은 컨퍼런스 리그·조별·토너먼트",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회는 2020-21까지 원정 다득점·연장, 2021-22부터 원정 다득점 없이 연장(2020 챔스 PO PAOK전 두 경기, 2024 컨퍼런스 8강 1차전 애스턴 빌라전)",
    "시즌 구분: 몽펠리에는 7월 10일 기준(2012.7.28 트로페 데 샹피옹 = 2012-13), 크라스노다르는 7월 1일 기준(2021.7.25 개막전 = 2021-22)이되 2020년 7월(코로나로 미뤄진 2019-20 리그)은 2019-20, 나머지 클럽은 8월 1일 기준. 클럽 구분: 2011.7.1 몽펠리에, 2014.7.13 뉴캐슬, 2015.8.19 마르세유, 2017.8.31 생테티엔, 2019.7.26 크라스노다르, 2022.4.6 몽펠리에, 2022.7.10 릴, 2025.7.1 올림피아코스, 2026.1.1 낭트, 2026.9.14 볼로스(Transfermarkt 이적 날짜, 경기 클럽과 경계 불일치 0)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 리그1 우승 2011-12(몽펠리에), 쿠프 드 프랑스 준우승 2015-16(마르세유). 대표팀(2014 월드컵 참가)은 뺌",
]
NOTE = "\n".join(l for l in NOTE_LINES if l)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "MAN", "elk", "elq", "ecg", "eck", "lg", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

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
    allr = sorted(rs, key=tkey)
    for a, b in zip(allr, allr[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
mm_ = {m[0]: m for m in M}
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[9] in mm_ and (mm_[r[9]][1] != r[1] or mm_[r[9]][2] != r[3]): problems.append(("상대/대회 M 불일치", r[9], r[1], r[3], mm_[r[9]][1:3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
if "--stat" in sys.argv:
    for n, v in ST.items(): print(n, v)
    print(NG, NGo, NPK, NA, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM 도움", TM_A, TM_A_API)
    for j in judg: print(" ", j)
    for p in post_gap_log: print(" post", p)
    for f in fm_only_seen: print(" fm", f)
    print("FM diff", FM_DIFF, FM_N_G, FM_N_GAMES, "FotMob 경기 기록 없는 경기 골", NO_FM_G)
    print("seasons", sorted(SEAS.items()), sorted(SEAS_MIN.items()))
    print("problems", problems)
    for c in cross:
        if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
    print("대조 요약", collections.Counter((c[0], c[4] if "골" in c[0] and len(c) > 4 else "") for c in cross))
    sys.exit(0)
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(OUT_JS, "w", encoding="utf-8").write(f"const CAB_E={J(E)};\nconst CAB_M={J(M)};\nconst CAB_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "post_gap_tm_only": post_gap_log,
           "fm_only": fm_only_seen, "stoppage_from_fotmob": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "fotmob_goal_diffs": FM_DIFF, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems), problems)
