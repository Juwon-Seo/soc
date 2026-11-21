# build_benyedder.py 뒤쪽: 동료 대조·클럽·시즌·설명(NOTE)·일관성 점검·출력 (build_benyedder.py가 exec로 읽음)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음, 보고용)
def is_me(n): return bool(re.search(r"Ben Yedder", str(n)))
def same_vals(a, b): return (a[5], a[6], a[2], a[12], a[3], a[7], a[14:]) == (b[5], b[6], b[2], b[12], b[3], b[7], b[14:])
cross = []
MATES = collections.Counter()
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and is_me(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2], key=lambda r: (not same_vals(r, x), abs(r[4] - x[4])))
            cross.append(("동료 도움→벤 예데르 골", b, x[9], x[4], "일치" if hit and same_vals(hit[0], x) else ("값 다름" if hit else "벤 예데르 골 없음"), x[1:9], hit[0][1:9] if hit else None))
    # 같은 날 같은 상대 출전 행 = 같은 팀 동료
    mates_d = {mm[0] for mm in om for m in M if mm[0] == m[0] and same_team(mm[1], m[1])}
    if mates_d:
        MATES[b] = len(mates_d)
        for r in E:
            if r[9] not in mates_d: continue
            if r[0] == "a":
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                if hit: cross.append(("벤 예데르 도움→동료 골", b, r[9], r[4], "일치" if same_vals(hit[0], r) else "값 다름", r[1:9], hit[0][1:9]))
            for x in oe:
                if x[9] == r[9] and same_team(x[1], r[1]) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                    cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
        # Transfermarkt에서 동료 골에 벤 예데르 도움이 있는데 여기서 뺀 경우 / 동료가 벤 예데르 골을 도운 경우
        for gid, evs in EVS.items():
            if gid not in G or ldate(G[gid]) not in mates_d: continue
            d = ldate(G[gid])
            for e in evs:
                if e["scorer_id"] == ME and e["assist_player"] and not any(x[0] == "a" and x[9] == d and is_me(x[13]) for x in oe):
                    if any(x[0] == "g" or x[0] == "a" for x in oe if x[9] == d):
                        cross.append(("참고: Transfermarkt 도움(벤 예데르 골)", b, d, e["minute"], e["assist_player"], e["assist_type"]))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
    # 상대로 만난 경우(같은 날, 상대 이름에 툴루즈·세비야·모나코 등): Elo 값 비교는 생략(우리 팀 값이 아님)
_seen = set(); cross = [c for c in cross if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("touby", "2016-07-30", "툴루즈", "툴루즈", "2010~2016"), ("sevby", "2019-08-14", "세비야", "세비야", "2016~2019"),
         ("monby", "2025-03-16", "AS 모나코", "모나코", "2019~2024"), ("sepby", "2025-09-08", "세파한", "세파한", "2025"),
         ("sakby", "2026-01-06", "사카리아스포르", "사카리아스포르", "2025"), ("wydby", None, "위다드 카사블랑카", "위다드", "2026")]
TMCLUB = {"415": "touby", "368": "sevby", "162": "monby", "4947": "sepby", "2463": "sakby", "6603": "wydby"}
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
CN = {k: n for k, u, n, sh, y in CLUBS}
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "sevby":      # 7월 10일 기준(2018.7.26 유로파 예선 = 2018-19)
        s_ = y if d[5:] >= "07-10" else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    if d.startswith("2020-08") and club != "monby": return "2019-20"
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
SELF_A = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == ME and e["scorer_id"] == ME)
RES_G = sum(int(g["goals"] or 0) for g in RESERVE); RES_N = len(RESERVE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
KO = {"FC Lorient": "로리앙", "Entente Sannois Saint-Gratien": "상누아 생그라티앵", "SD Formentera": "포르멘테라", "Újpest FC": "우이페슈트",
      "Quevilly Rouen Métropole": "케비이 루앙", "Stade Brestois 29": "브레스트"}
def jl(reason):
    return ", ".join(f"{d_(j[1])} {KO.get(j[2], j[2])}전 {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
FMG = [(gid, e) for gid, evs in EVS.items() if gid in G and gid in FME for e in evs if e["scorer_id"] == ME and e["own_goal"] != "1"]
FM_N_G = len(FMG); FM_N_GAMES = len({gid for gid, e in FMG})

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
st_txt = ", ".join(f"{n} {c3(v)}" for n, v in ST.items())
NOTE_LINES = [
    f"위삼 벤 예데르(툴루즈·세비야·AS 모나코·세파한·사카리아스포르·위다드 카사블랑카)의 클럽 공식 경기 {NG}경기({d_(first[0])} 파리 생제르맹전 ~ {d_(last[0])} 우니옹 투아르가전)에서 나온 {NGo}골 {NA}도움, 친선경기·프랑스 대표팀·2군 경기 제외",
    f"클럽별 경기·골·도움: {st_txt}. 출전 분 합계 {MIN_TOT:,}분",
    "현역 표시: 2026.7.5 위다드와 계약이 끝난 뒤 소속 팀이 없음(Transfermarkt 2026.7.6 '무소속'). 은퇴 발표가 없어 현역으로 둠(산초·팔카오 선례). 2024.7~2025.3(모나코 계약 종료 뒤)에도 소속 팀 없이 쉼",
    f"넣지 않은 시즌·팀: UJA 알포르빌 2009-10(프랑스 4부 CFA, 아마추어 리그 — 위키백과 23경기 9골, 프랑스어 위키백과 10도움; Transfermarkt에는 출전 기록이 없음), 툴루즈 2군 2010-13(5부 CFA 2, Transfermarkt {RES_N}경기 {RES_G}골, 도움 자료 없음). 프로 리그 시즌만 셈",
    "소속 팀 리그: 리그1·라리가·이란 1부(페르시안 걸프 프로리그)·모로코 1부(보톨라 프로)는 프로 1부, 사카리아스포르(2025-26)는 튀르키예 2부(TFF 1. 리그, 프로 리그)이고 위키백과·Transfermarkt 통산 기록에 들어 있어 넣음",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음. 클럽별 경기·골 수는 영어 위키백과와 같음(위다드는 Transfermarkt 23경기, 영어 위키백과·FotMob 22경기: 2026.5.17 스론컵 32강 라자 베니 멜랄전 5분 출전이 FotMob에 없음 — Transfermarkt 기준으로 넣음)",
    f"골 {NGo}개 중 PK {NPK}개(Transfermarkt 골 유형 'Penalty', 선수 경기 성적 PK 골 수와 경기마다 같음). 자책골 없음. 골 {FM_N_G}개 모두 FotMob 경기 기록과 대조함(수·골 뒤 스코어·PK·분 같음, 분 차이 1분 이하)",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움(단일 출처 허용), 그 뒤는 Transfermarkt와 FotMob이 같이 적은 도움을 기준으로 하고, 한쪽에만 있는 도움은 다른 출처 2곳이 확인한 것만 넣음. 사카리아스포르 2경기(2025.10.18 아다나 데미르스포르전 1개·2025.11.8 세리크스포르전 2개)는 FotMob 경기 기록에 도움자가 비어 있지만 FotMob 선수 경기 목록의 도움 수가 Transfermarkt와 같아(FotMob 통산 사카리아스포르 3도움) 일치로 봄",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A}개 − PK 유도 {EX['PK 유도']}개 − 2014.8 이후 Transfermarkt에만 있어 뺀 {EX['2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)'] + EX['슈팅 리바운드(기사)']}개. Transfermarkt 선수 경기 성적의 도움도 {TM_A_API}개(본인 PK 골에 본인 도움으로 적힌 {SELF_A}개는 원래 도움 수에 들어 있지 않음). FotMob에만 있는 도움은 없음",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "Transfermarkt에만 있어 뺀 도움: " + jl("슈팅 리바운드(기사)") + "(벤 예데르 헤더가 골대에 맞고 나온 것을 넣은 골, Sky Sports·maxifoot), " + jl("2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)") + "(기사 1곳 이하만 도움을 적음)",
    "Transfermarkt에만 있지만 기사 2곳이 확인해 넣은 도움: 2017.5.5 레알 소시에다드전 41분 사라비아(벨가 통신·FourFourTwo), 2019.12.4 툴루즈전 84분 젤송 마르팅스(maxifoot·AS 모나코 구단 기사), 2020.1.4 랭스전(쿠프 드 프랑스) 61분 케이타 발데(Goal.com·beIN Sports)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(FotMob은 2012-13·2013-14 도움 칸이 거의 비어 있음)",
    "날짜는 경기 현지 날짜(Transfermarkt 리포트·일정 날짜, 이란·튀르키예·모로코 경기도 현지 날짜와 같음). 승부차기 경기는 승부차기 전 스코어 기준",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값({ELO_SRC['같은 경기 다른 선수 자료']}개 기록), 직접 추정({ELO_SRC['직접 추정']}개), 기존 선수 자료의 같은 팀·같은 시즌 값({ELO_SRC['기존 팀×시즌 값']}개), 그 시즌 최종 순위를 리그 모형에 넣은 값({ELO_SRC['순위표+리그 모형']}개) 순으로 씀",
    "리그 수준: 리그1·라리가·에레디비시는 다른 선수 자료의 순위값, 리그2는 지냑·고미스 자료와 같은 20팀 순위값, 프랑스 3부(나시오날)는 1311 + 2부 흩어짐 × 순위 곡선, 프랑스 4부는 1220, 세군다는 22팀 고정값, 스페인 3부(세군다 B)는 1350, 러시아는 에투 자료 모형(평균 1520·흩어짐 55)(모두 기존 선례)",
    "튀르키예 2부(TFF 1. 리그) 2025-26: 쉬페르리그 평균 1567에서 1·2부 차 162를 뺀 평균에 2부 흩어짐으로 최종 순위를 넣은 추정(판페르시·발부에나 선례)",
    "모로코 1부(보톨라 프로) 2025-26: 기존 모형이 없어 평균 1440·흩어짐 63으로 최종 순위(Transfermarkt 표, 우승 MAS 페스 확인)를 넣은 추정(근거 약함; 다른 선수 자료 위다드 2024-25 3위 1500에 3위 값이 맞도록 평균을 정함). 이란 1부 에스테그랄 2024-25는 다른 선수 자료 값 1440",
    "직접 추정(모두 '추정'): " + "; ".join(f"{o} {e} — {lv}" for o, e, lv in MAN_USED),
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 델 레이·하즈피컵·스론컵은 16강까지·8강·준결승·결승(쿠프 드 프랑스 5~7라운드·32강, 쿠프 드 라 리그 3라운드는 16강까지). 수페르코파(2016 두 경기 결승·2018 단판 결승)는 국내컵 결승 비중. 챔스 예선·플레이오프는 챔스 예선, 유로파 예선은 예선, 유로파 32강('intermediate stage')·16강은 유로파 토너먼트. CAF 컨페더레이션컵(아프리카 대륙 2부 대회)은 따로 비중이 없어 코파 수다메리카나와 같은 대륙 2부 대회 비중(조별 15, 8강 20)을 씀",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회는 2020-21까지 원정 다득점·연장, 2021-22부터 원정 다득점 없이 연장, 코파 델 레이는 2018-19까지 원정 다득점·연장. 못 뛴 다른 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 세비야는 7월 10일 기준(2018.7.26 유로파 예선 우이페슈트전 = 2018-19), 모나코의 2020년 8월 경기(2020-21 리그1 개막)는 2020-21, 나머지는 8월 1일 기준. 클럽 구분: 2016.7.30 세비야, 2019.8.14 모나코, 2025.3.16 세파한, 2025.9.8 사카리아스포르, 2026.1.6 위다드(Transfermarkt 이적 날짜, 경기 클럽과 경계 불일치 0)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 리그1 득점왕 2019-20, 코파 델 레이 득점왕 2016-17, 쿠프 드 프랑스 득점왕 2021-22. 클럽 우승 기록 없음. 대표팀(UEFA 네이션스리그 2020-21)은 뺌",
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
    print(NG, NGo, NPK, NA, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM 도움", TM_A, TM_A_API, "SELF", SELF_A)
    for j in judg: print(" ", j)
    for p in post_gap_log: print(" post", p)
    for f in fm_only_seen: print(" fm", f)
    print("seasons", sorted(SEAS.items()), sorted(SEAS_MIN.items()))
    print("problems", problems)
    print("mates", MATES)
    for c in cross:
        if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
    print("대조 요약", collections.Counter((c[0], c[4] if "골" in c[0] and len(c) > 4 else "") for c in cross))
    for r in E:
        if len(r) > 14 or r[10]: print("  tie/et", r)
    sys.exit(0)
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(OUT_JS, "w", encoding="utf-8").write(f"const BEN_E={J(E)};\nconst BEN_M={J(M)};\nconst BEN_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "post_gap_tm_only": post_gap_log,
           "fm_only": fm_only_seen, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems), problems)
