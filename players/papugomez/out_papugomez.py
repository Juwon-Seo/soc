# build_papugomez.py 뒤쪽: 동료 대조·클럽·시즌·설명(NOTE)·일관성 점검·출력 (build_papugomez.py가 exec로 읽음)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
SHOT = "슈팅 리바운드('Shot on goal')"
G_BYDATE = {ldate(g): g["competitionId"] for g in GAMES}
MATE = {"ili.js": ("Iličić", ("Ilicic", "Iličić")), "isc.js": ("Isco", ("Isco",))}
def is_me(n): return bool(re.search(r"Papu|Alejandro G[oó]mez|Alejandro Gomez", str(n)))
def same_vals(a, b): return (a[5], a[6], a[2], a[12], a[3], a[7], a[14:]) == (b[5], b[6], b[2], b[12], b[3], b[7], b[14:])
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and is_me(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            cross.append(("동료 도움→고메스 골", b, x[9], x[4], "일치" if hit and same_vals(hit[0], x) else ("값 다름" if hit else "고메스 골 없음"), x[1:9], hit[0][1:9] if hit else None))
    if b in MATE:
        nm, tk = MATE[b]
        for r in E:
            if r[0] == "a" and any(t in str(r[13]) for t in tk):
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                cross.append(("고메스 도움→동료 골", b, r[9], r[4], "일치" if hit and same_vals(hit[0], r) else ("값 다름" if hit else "동료 골 없음"), r[1:9], hit[0][1:9] if hit else None))
        # Transfermarkt에서 동료가 고메스 골을 도왔는데 동료 파일에 그 도움이 없는 경우 / 고메스가 동료 골을 도왔는데 여기서 뺀 경우
        for gid, evs in EVS.items():
            if gid not in G: continue
            d = ldate(G[gid])
            for e in evs:
                if e["scorer_id"] == ME and any(t in e["assist_player"] for t in tk):
                    if not any(x[0] == "a" and x[9] == d and is_me(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움(고메스 골)이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
                if e["assist_id"] == ME and any(t in e["scorer"] for t in tk):
                    if not any(r[0] == "a" and r[9] == d and abs(r[4] - mins(e["minute"])[0]) <= 2 for r in E):
                        has = [x for x in oe if x[0] == "g" and x[9] == d and abs(x[4] - mins(e["minute"])[0]) <= 2]
                        cross.append(("Transfermarkt 고메스 도움(동료 골)을 뺌", b, d, e["minute"], e["assist_type"], "동료 골 행 있음" if has else "동료 골 행 없음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) if G_BYDATE.get(r[9]) in SA_DOM else same_team(x[1], r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or (G_BYDATE.get(m[0]) not in SA_DOM and toks(mm[1]) & toks(m[1]))) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
_seen = set(); cross = [c for c in cross if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("arspg", "2009-01-29", "아르센알 데 사란디", "아르센알", "2005~2008"), ("slzpg", "2010-07-21", "산로렌소", "산로렌소", "2009~2010"),
         ("ctnpg", "2013-08-02", "카타니아", "카타니아", "2010~2013"), ("metpg", "2014-09-01", "메탈리스트 하르키우", "메탈리스트", "2013~2014"),
         ("atapg", "2021-01-26", "아탈란타", "아탈란타", "2014~2021"), ("sevpg", "2023-09-29", "세비야", "세비야", "2021~2023"),
         ("mnzpg", "2025-07-11", "몬차", "몬차", "2023"), ("padpg", "2026-09-28", "파도바", "파도바", "2025~2026"),
         ("fvpg", None, "포르테 비르투스", "포르테 비르투스", "2026~")]
TMCLUB = {"4673": "arspg", "1775": "slzpg", "1627": "ctnpg", "6414": "metpg", "800": "atapg", "368": "sevpg", "2919": "mnzpg", "3037": "padpg", "90721": "fvpg"}
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
CN = {k: n for k, u, n, sh, y in CLUBS}
SCAL = ("arspg", "slzpg")
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    if club == "atapg":     # 7월 10일 기준(2018.7.26 유로파 예선 = 2018-19), 단 2020.7~8월(미뤄진 2019-20 리그·챔스 8강)은 2019-20
        if "2020-07-01" <= d < "2020-09-01": return "2019-20"
        s_ = y if d[5:] >= "07-10" else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    if d.startswith("2020-08"): return "2019-20"
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for k, u, n, sh, y in CLUBS)
for m in M: ST[CN[club_of(m[0])]][0] += 1; ST[CN[club_of(m[0])]][3] += m[3]
for r in E: ST[CN[club_of(r[9])]][1 if r[0] == "g" else 2] += 1
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
KO = {"AC Cesena": "체세나", "US Palermo": "팔레르모", "Brescia Calcio": "브레시아", "Novara Calcio 1908": "노바라", "SSC Napoli": "나폴리",
      "Parma FC": "파르마", "Genoa CFC": "제노아", "Chievo Verona": "키에보", "Atalanta BC": "아탈란타", "Volyn Lutsk": "볼린",
      "Dynamo Kyiv": "디나모 키이우", "Metalurg Zaporizhya": "메탈루르흐 자포리자", "Chornomorets Odesa": "초르노모레츠",
      "ACF Fiorentina": "피오렌티나", "AS Roma": "로마", "Udinese Calcio": "우디네세", "Torino FC": "토리노", "FK Sarajevo": "사라예보",
      "SS Lazio": "라치오", "AC Milan": "밀란", "GNK Dinamo Zagreb": "디나모 자그레브", "CA Osasuna": "오사수나", "CA Lanús": "라누스",
      "CA Banfield": "반필드", "CD Motagua Tegucigalpa": "모타과", "Hellas Verona": "베로나", "Parma Calcio 1913": "파르마",
      "Catania Calcio": "카타니아", "Inter Milan": "인테르", "CA Independiente": "인데펜디엔테", "Racing Club": "라싱",
      "Club Atlético Gimnasia y Esgrima (Jujuy)": "힘나시아 후후이", "CA Colón": "콜론", "US Sassuolo": "사수올로"}
def jl(reason):
    return ", ".join(f"{d_(j[1])} {KO.get(j[2], j[2])}전 {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
FMG = [(gid, e) for gid, evs in EVS.items() if gid in G and gid in FME for e in evs if e["scorer_id"] == ME and e["own_goal"] != "1"]
FM_DIFF = []
for gid, e in FMG:
    f = fm_ev(gid, e["score_home_away_after"])
    if not f or f["papu_scorer"] != "1": FM_DIFF.append((gid, ldate(G[gid]), e["minute"], "FotMob에 같은 스코어 고메스 골 없음")); continue
    fmin = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(fmin - mins(e["minute"])[0]) > 1: FM_DIFF.append((gid, ldate(G[gid]), e["minute"], f"FotMob {f['time']}" + (f"+{f['overloadTime']}" if f["overloadTime"] else "")))
    if ("pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower()) != (e["goal_desc"] == "Penalty"): FM_DIFF.append((gid, ldate(G[gid]), e["minute"], "PK 표시 다름"))
FM_N_G = len(FMG); FM_N_GAMES = len({gid for gid, e in FMG})
ARG_DATE_SHIFT = sum(1 for g in GAMES if g["club_id"] in ("4673", "1775") and g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local"])

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
st_txt = ", ".join(f"{n} {c3(v)}" for n, v in ST.items())
NOTE_LINES = [
    f"파푸 고메스(아르센알 데 사란디·산로렌소·카타니아·메탈리스트·아탈란타·세비야·몬차·파도바·포르테 비르투스)의 클럽 공식 경기 {NG}경기({d_(first[0])} 힘나시아 라플라타전 ~ {d_(last[0])} 두바이 시티전)에서 나온 {NGo}골 {NA}도움, 친선경기·아르헨티나 대표팀(A·U-20) 제외",
    f"클럽별 경기·골·도움: {st_txt}. 출전 분 합계 {MIN_TOT:,}분",
    "현역(포르테 비르투스, UAE 2부): 2026.11.6 두바이 시티전까지 반영",
    "도핑 징계로 2년 가까이 경기 기록이 없음: 세비야 시절(2022년 10~11월) 도핑 검사에서 금지 약물 테르부탈린이 나와 2023.10.20 2년 출전 정지가 발표됨. 몬차에서 2경기(2023.10.2·10.8)를 뛴 뒤 2023.10.9부터 2025.11.21까지 공식 경기 출전이 없고(몬차와 계약 종료, 징계 중 레나테에서 훈련만 함), 2025년 7월 파도바(세리에B)와 계약해 징계가 끝난 뒤 2025.11.22 베네치아전으로 복귀",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(클럽 공식 경기 {NG}경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음. 클럽별 경기 수는 Transfermarkt·스페인어 위키백과와 같음(영어·이탈리아어 위키백과는 산로렌소 58경기 9골)",
    "소속 팀 리그: 아르헨티나 1부·세리에A·우크라이나 1부·라리가는 프로 1부, 파도바(2025-26)는 세리에B(이탈리아 2부, 프로)라 넣음. 포르테 비르투스(2026-27)는 UAE 2부(퍼스트 디비전) 팀으로 프로 리그인지 자료에 분명하지 않지만, Transfermarkt 통산 기록과 이탈리아어 위키백과 선수 정보(3경기 2골)가 이 시즌을 통산에 넣고 있어 넣음",
    "산로렌소 2009-10: 영어·이탈리아어 위키백과·FotMob 통산은 산로렌소 58경기 9골, Transfermarkt는 57경기 8골. 산로렌소 기록 사이트(estadisticascasla.com)는 57경기 9골로, 2010.3.20 콜론전(2-2) 89분 동점골을 Transfermarkt가 콜론 선수 리카르도 고메스의 골로 잘못 적은 것으로 확인됨(경기 기록: 90분 고메스 골, 91분 유니폼을 벗는 세리머니로 퇴장; 디아리오 데 쿠요 경기 기사도 고메스의 마지막 분 동점골). 이 골을 넣음(분은 Transfermarkt 89분, 골 전 1-2). 위키백과의 1경기 차이는 경기별 출처가 없어 넣지 않음",
    f"골 {NGo}개 중 PK {NPK}개(Transfermarkt 골 유형 'Penalty', 선수 경기 성적 PK 골 수와 경기마다 같음). 자책골 없음. 2010-11 이후 골 {FM_N_G}개({FM_N_GAMES}경기)는 FotMob 경기 기록과 대조함(수·골 뒤 스코어·PK 같음; 2012.8.18 사수올로전(코파 이탈리아)은 Transfermarkt 73분·FotMob 71분이라 Transfermarkt를 씀). 2010년 전 아르헨티나 경기는 FotMob 자료가 없음",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움(단일 출처 허용), 그 뒤는 Transfermarkt와 FotMob 경기 기록이 같이 적은 도움을 기준으로 하고, 한쪽에만 있는 도움은 다른 출처 2곳이 확인한 것만 넣음. UAE 2부 경기는 Transfermarkt 도움이 없음(FotMob은 포르테 비르투스 경기 자료가 없음)",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 슈팅 리바운드 {EX[SHOT]}개 − 고메스가 핸드볼로 내준 PK 줄 1개 − 2014.8 이후 Transfermarkt에만 있고 다른 출처 2곳으로 확인되지 않은 {EX['2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)']}개 + FotMob에만 있고 기사 2곳이 확인한 1개(2019.3.31 파르마전 24분 파샬리치). Transfermarkt 선수 경기 성적의 도움은 {TM_A_API}개(리포트의 2022.8.12 오사수나전 74분 'Handball by Papu Gómez'는 고메스가 핸드볼 반칙으로 내준 PK라 도움이 아님)",
    "PK 유도로 뺀 도움: " + jl("PK 유도") + ". 상대 자책골 유도로 뺀 도움: " + jl("상대 자책골 유도") + ". 슈팅 리바운드로 뺀 도움: " + jl("슈팅 리바운드('Shot on goal')"),
    "Transfermarkt에만 있어 뺀 도움: " + jl("2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)") + "(경기 기사에 고메스 도움 언급 없음). 2016.1.6 우디네세전 75분 달레산드로 골 도움은 FotMob에 없지만 Sports Mole 경기 기사와 이탈리아 문자 중계가 고메스 크로스로 적어 넣음",
    "FotMob에만 있어 뺀 도움: 2017.10.25 베로나전 50분 프로일러(다른 기록 사이트 1곳만 고메스 도움, 판타지 공식 도움은 다른 선수), 2012.9.26 아탈란타전 52분 스폴리(2014 이전이라 Transfermarkt 기준: 로디 코너킥 도움)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(FotMob은 2010-11~2013-14 도움 칸이 거의 비어 있고 2010년 이전 아르헨티나 경기 자료가 없음)",
    "날짜는 경기 현지 날짜. 아르헨티나 클럽 경기는 Transfermarkt 경기 시각(UTC)을 아르헨티나 시간(UTC−3)으로 바꾼 날짜(저녁 경기는 Transfermarkt 일정·리포트 날짜보다 하루 앞; 2009.10.16 로사리오 센트랄전은 경기 기사 날짜와 같음), 유럽 경기는 Transfermarkt 리포트 날짜, UAE 경기는 두바이 시간",
    "출전 분: Transfermarkt 그대로. 다만 연장 없이 바로 승부차기로 끝난 코파 수다메리카나 두 경기는 Transfermarkt가 120분 경기로 계산해 90분 기준으로 고침: 2009.11.4 8강 2차전 리버 플레이트(몬테비데오)전 120분 → 90분(선발 풀타임), 2007.11.14 준결승 2차전 리버 플레이트전 49분 → 19분(71분 교체 투입). 연장 경기(2012.12.4 치타델라전 코파 이탈리아, 2018.8.30 코펜하겐전 유로파 예선(연장 뒤 승부차기), 2021.3.3 바르셀로나전·2021.12.1 코르도바전·2021.12.15 안드라츠전 코파 델 레이, 2023.5.18 유벤투스전 유로파 준결승)은 연장 포함",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(일리치치·이스코 등) 값을 먼저 쓰고({ELO_SRC['같은 경기 다른 선수 자료']}개 기록), 없으면 직접 추정, 기존 선수 자료의 같은 팀·같은 시즌 값({ELO_SRC['기존 팀×시즌 값']}개), 그다음 그 시즌 최종 순위를 리그 모형에 넣은 값({ELO_SRC['순위표+리그 모형']}개)",
    "리그 수준: 아르헨티나 1부는 반시즌(아페르투라·클라우수라) Transfermarkt 순위표를 평균 1583·흩어짐 63 모형에 넣음(리그 경기는 그 경기가 속한 대회, 대륙 대회의 아르헨티나 상대는 그때 진행 중인 대회 순위). 아페르투라 2008은 3팀 결정전 뒤 최종 순위(보카 1·티그레 2·산로렌소 3). 통합표 시즌 키가 연도라 같은 팀이 한 해 두 대회 값이 다르면 평균(리켈메·포를란 선례). 브라질 세리에 A 2007은 기존 모형(평균 1598). 멕시코 2007-08(과달라하라)은 아페르투라·클라우수라 조별 표 승점 합 18팀 순위(2위)를 기존 멕시코 모형(1604.25 + 73.41 × 곡선)에 넣은 추정(리켈메 자료의 아틀라스 2007-08 15위와 같은 표)",
    "우크라이나 1부 2013-14는 셰브첸코 자료 모형(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333) − 73, 흩어짐 119; 계수 2012-13 9.500·2013-14 7.833·2014-15 10.000, kassiesa.net)으로 리그 평균 약 1441(추정). 순위는 Transfermarkt 표 = 영어 위키백과 최종 순위. 다른 선수 자료에 같은 팀·시즌 값이 있으면(드니프로 2위 1600·초르노모레츠 5위 1480) 그 값",
    "UAE 2부(퍼스트 디비전) 2026-27은 UAE 프로리그 평균 1440(이니에스타 자료 모형)에서 1·2부 차 162(일본 J2 선례)를 뺀 평균 1278에 2부 흩어짐으로 순위를 넣은 추정(근거 약함, 11월 중순 현재 순위: 알바타에 12위·두바이 시티 15위/15팀)",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED),
    "대회 비중: 코파 이탈리아·코파 델 레이·우크라이나컵은 16강까지·8강·준결승·결승. 레코파 수다메리카나 2008(보카전 두 경기)과 스루가 뱅크 챔피언십 2008(감바 오사카전 단판)은 국내컵 결승 비중(리켈메·호나우지뉴 선례). 리베르타도레스 2008 예선(미네로스전)·조별은 리베르타도레스 조별 비중, 코파 수다메리카나는 16강까지·8강·준결승·결승. 유로파 예선(2018 사라예보·하포엘 하이파·코펜하겐)은 예선, 유로파 32강('intermediate stage')·8강은 유로파 토너먼트, 준결승은 유로파 준결승. 챔스 2019-20 8강(파리 생제르맹전, 리스본 단판)은 챔스 8강",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회는 2020-21까지 원정 다득점·연장, 2021-22부터 원정 다득점 없이 연장, 코파 이탈리아 준결승은 원정 다득점·2차전 연장, 코파 수다메리카나·리베르타도레스는 원정 다득점 있고 연장 없이 승부차기(2007 결승 4-4 원정 다득점 우승, RSSSF), 레코파 2008은 리켈메 자료와 같게 원정 다득점 없이 연장(규정 미확인 추정). 못 뛴 다른 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 아르센알 데 사란디·산로렌소는 달력 연도(리켈메 보카 선례), 아탈란타는 7월 10일 기준(2018.7.26 유로파 예선 사라예보전 = 2018-19)이되 2020년 7~8월(미뤄진 2019-20 리그·챔스 8강)은 2019-20, 나머지 클럽은 8월 1일 기준. 클럽 구분: 2009.1.29 산로렌소, 2010.7.21 카타니아, 2013.8.2 메탈리스트, 2014.9.1 아탈란타, 2021.1.26 세비야, 2023.9.29 몬차, 2025.7.11 파도바, 2026.9.28 포르테 비르투스(Transfermarkt 이적 날짜, 경기 클럽과 경계 불일치 0)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: UEFA 유로파리그 2022-23(세비야), 코파 수다메리카나 2007·스루가 뱅크 챔피언십 2008(아르센알 데 사란디; Transfermarkt 시즌 표기 06/07·07/08). 대표팀 우승(월드컵 2022·코파 아메리카 2021·피날리시마 2022·U-20 월드컵 2007)과 세리에A 2019-20 올해의 미드필더(표 항목 없음)는 뺌",
]
NOTE = "\n".join(l for l in NOTE_LINES if l)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "lg", "TM "]:
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
    print("FM diff", FM_DIFF, FM_N_G, FM_N_GAMES)
    print("seasons", sorted(SEAS.items()), sorted(SEAS_MIN.items()))
    print("problems", problems)
    for c in cross:
        if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
    print("대조 요약", collections.Counter((c[0], c[4] if "골" in c[0] and len(c) > 4 else "") for c in cross))
    sys.exit(0)
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(OUT_JS, "w", encoding="utf-8").write(f"const PAP_E={J(E)};\nconst PAP_M={J(M)};\nconst PAP_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "post_gap_tm_only": post_gap_log,
           "fm_only": fm_only_seen, "added_goal": ADD_GOAL, "minute_fixes": MIN_FIX, "cross_check": cross, "elo_sources": ELO_SRC,
           "arg_averages": ARG_AVG, "fotmob_goal_diffs": FM_DIFF, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems), problems)
