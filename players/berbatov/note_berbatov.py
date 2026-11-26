"""베르바토프 설명(NOTE) 문구 — build_berbatov.py가 globals()를 넘겨 부름"""
import collections

TEAMMATE = {"blk.js": "발라크", "snb.js": "슈나이더", "len.js": "레넌", "gig.js": "긱스", "ron.js": "호날두", "roo.js": "루니",
            "val.js": "발렌시아", "crr.js": "카라스코", "duf.js": "더프", "fal.js": "팔카오"}

KO = {"Levski Sofia": "레프스키 소피아", "Chennaiyin FC": "첸나이인 FC", "Manchester City": "맨체스터 시티", "Chelsea FC": "첼시",
      "Sunderland AFC": "선덜랜드", "Burnley FC": "번리", "Eintracht Frankfurt": "아인트라흐트 프랑크푸르트", "Portadown FC": "포타다운",
      "Constructorul Chisinau": "콘스트룩토룰 키시너우", "MTK Hungária FC": "MTK 헝가리아", "Hertha BSC": "헤르타 BSC",
      "FC Schalke 04": "샬케 04", "Birmingham City": "버밍엄 시티", "Liverpool FC": "리버풀", "FC Sochaux-Montbéliard": "소쇼",
      "FC Lorient": "로리앙", "1.FC Kaiserslautern": "카이저슬라우테른", "RC Lens": "랑스", "Everton FC": "에버턴",
      "Swansea City": "스완지 시티", "Arsenal FC": "아스널"}
def ko(n): return KO.get(n, n)
TEAMMATE_EN = {"blk.js": "Ballack", "snb.js": "Schneider", "len.js": "Lennon", "gig.js": "Giggs", "ron.js": "Ronaldo", "roo.js": "Rooney",
               "val.js": "Valencia", "crr.js": "Carrasco", "duf.js": "Duff", "fal.js": "Falcao"}
def clean(n): return n.replace("\u200e", "").strip()

def make_note(V):
    M, E, ST, CN = V["M"], V["E"], V["ST"], V["CN"]
    judg, SRC, SRC_A = V["judg"], V["ELO_SRC"], V["SRC_A"]
    def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
    def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
    first, last = M[0], M[-1]
    pkx = [j for j in judg if j[0] == "도움 제외" and j[5].startswith("PK 유도")]
    sog = [j for j in judg if j[0] == "도움 제외" and j[5].startswith("슈팅")]
    ogx = [j for j in judg if j[0] == "도움 제외" and j[5] == "상대 자책골 유도"]
    selfa = [j for j in judg if j[0].startswith("도움 아님")]
    man = sorted({(o, v[1], v[2]) for (o, d), v in V["ELO_LOG"].items() if v[0] == "man"})
    fmo = V["FM_ONLY_A"]
    tmates = collections.defaultdict(lambda: [0, 0])
    for c in V["CROSS"]:
        if c[1] in TEAMMATE and c[0] == "타인 도움→베르바토프 골": tmates[c[1]][0] += 1
        if c[1] in TEAMMATE and c[0] == "베르바토프 도움→타인 골" and TEAMMATE_EN[c[1]] in c[4]: tmates[c[1]][1] += 1
    blank = V["TM_A_TYPES"]["(빈칸)"]
    L = [
        f"디미타르 베르바토프(CSKA 소피아·바이어 레버쿠젠·토트넘 홋스퍼·맨체스터 유나이티드·풀럼·AS 모나코·PAOK·케랄라 블래스터스)의 클럽 공식 경기 {V['NG']}경기({d_(first[0])} {ko(first[1])}전 ~ {d_(last[0])} {ko(last[1])}전)에서 나온 {V['NGo']}골 {V['NA']}도움(PK 골 {V['NPK']}개), 친선경기·불가리아 대표팀·레버쿠젠 2군 제외",
        "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {V['MIN_TOT']:,}분",
        "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부, 리포트 골·도움 수가 선수 경기 성적과 경기마다 같음). 토트넘부터 마지막까지 클럽·시즌·대회별 경기·골은 영어·불가리아어 위키백과와 같고, 맨유 2010-11부터는 FotMob 경기 기록(골 54경기)과 대조해 골 수·PK가 한 경기(아래 에비앙전)만 빼고 모두 같음",
        "뺀 기록: 레버쿠젠 2군(2001년 1~5월 4부 오버리가 노르트라인, 프로 리그 아님) 7경기 6골, 대표팀(A·21세 이하). CSKA 소피아의 불가리아컵은 Transfermarkt에 1999년 결승 1경기만 있어 그 경기만 넣음 — 위키백과의 불가리아컵 9경기 5골(1998-99 5경기 3골·1999-2000 4경기 2골)과 2000-01 리그 1경기는 경기별 출처가 없어 넣지 못함(CSKA 합계 Transfermarkt 57경기 33골, 위키백과 66경기 38골). 레버쿠젠 2005-06 DFL-리가포칼 1경기는 Transfermarkt에 있어 넣음(위키백과 합계 201경기는 이 경기를 빼고 셈)",
        "모든 소속 팀-시즌이 1부 프로 리그(불가리아 A그룹·분데스리가·프리미어리그·리그1·그리스 슈퍼리그·인도 슈퍼리그). 인도 슈퍼리그 2017-18은 I리그와 함께 1부로 운영된 프로 리그(2022-23부터 단독 1부)라 셈",
        "출전 분: Transfermarkt 그대로(빈칸 없음, 90분 추정 없음). 날짜는 경기 현지 날짜(인도는 인도 시간)",
        f"골: 2004.10.19 AS 로마전(챔스 조별) 26분 베르바토프 자책골은 골이 아님. 2015.3.7 에비앙전(리그1) 35분 골은 FotMob이 에비앙 압달라 자책골로 적었지만 Transfermarkt·maxifoot·ESPN 경기 기록이 모두 베르바토프 골(34~35분)로 적어 넣음. PK 골 {V['NPK']}개는 Transfermarkt 골 유형 'Penalty'(FotMob 자료가 있는 경기는 FotMob과 같음). 골 시각 차이(2012.9.15·2013.2.23 전반 추가시간 골)는 Transfermarkt 표기",
        f"도움: 2014년 8월 전은 Transfermarkt 리포트 단일 출처를 씀(클로제·벨한다 선례). 2014년 8월 뒤 도움은 1개(2014.9.16 레버쿠젠전 61분 무티뉴 골, FotMob 경기 기록과 같음). Transfermarkt 도움 {V['N_TM_A']}개 − PK 유도 {len(pkx)}개 − 슈팅 리바운드('Shot on goal') {len(sog)}개(" + ", ".join(f"{d_(j[1])} {ko(j[2])}전 {j[3]}분 {clean(j[4])}" for j in sog) + f") − 상대 자책골에 준 도움 {len(ogx)}개(" + ", ".join(f"{d_(j[1])} {ko(j[2])}전 {j[3]}분 {j[4]} 자책골" for j in ogx) + f") = {V['NA']}개. PK 유도: " + ", ".join(f"{d_(j[1])} {ko(j[2])}전 {j[4]}" for j in pkx) + f". 본인 PK 골에 붙은 본인 도움 표기 {len(selfa)}개(" + ", ".join(f"{d_(j[1])} {ko(j[2])}전 {j[3]}분" for j in selfa) + f")는 도움이 아님. 유형 칸이 빈 Transfermarkt 도움 {blank}개(대부분 2000~2008)는 일반 도움으로 셈",
        "FotMob에만 있는 도움 " + str(len(fmo)) + "개는 2014년 전 Transfermarkt 기준이라 넣지 않음: " + ", ".join(f"{d_(x[1])} {ko(x[2])}전 {x[3]}분" for x in fmo) + ". 2011.10.25 올더숏전(리그컵) 41분 오언 골 도움은 FotMob 경기 기록에 도움 자료가 없지만 2014년 전 Transfermarkt 도움이라 넣음. FotMob 경력 합계(맨유 24·모나코 6도움)와 Transfermarkt(27·8)의 차이는 위 PK 유도·리바운드 등",
        "2007.4.12 세비야전(UEFA컵 8강 2차전) Transfermarkt 리포트는 3분 말브랑크 자책골을 '1:0'으로 잘못 표시해 스코어가 어긋남 — 최종 2-2·전반 0-2에 맞춰 0-1(3분)·0-2(8분)·1-2(65분 디포, 베르바토프 도움)·2-2(66분 레넌)로 셈",
        f"상대 Elo는 같은 경기를 다룬 다른 선수 자료, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표, 위키백과로 확인)를 기존 리그 순위값·리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
        f"리그 모형(추정 표시): 불가리아 A그룹 1998-99~2000-01은 기존 모형이 없어 1위 1480 ~ 최하위 1300 직선(다른 선수 자료의 불가리아 1·2위 1480, 3~5위 1450, 6위 1420에 맞춘 선, 근거 약함). 그리스 슈퍼리그 2015-16은 발부에나·마린 자료와 같은 국가 계수 회귀(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119)에 그리스 보정 {V['GR_K']:+.0f}점(계수 2014-15 6.200·2015-16 5.400·2016-17 5.800, kassiesa.net·위키백과) → 리그 평균 {V['gr_mean']('2015-16'):.0f}, 16팀 정규리그 순위(위키백과 확인). 인도 슈퍼리그 2017-18은 델 피에로·말루다·포를란 자료와 같은 1위 1300 ~ 꼴찌 1200 직선(정규리그 순위). 2. 분데스리가는 다른 선수 자료 순위값 사이 직선",
        "직접 추정(모두 '추정' 또는 같은 리그 순위값): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in man),
        "대회 비중: DFB-포칼·FA컵·잉글랜드 리그컵·쿠프 드 프랑스·쿠프 드 라 리그·그리스컵·불가리아컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; FA컵 6라운드·재경기와 리그컵 5라운드는 8강), DFL-리가포칼은 첫 경기 8강·준결승, 커뮤니티 실드는 국내컵 결승, UEFA컵 예선·1라운드는 유로파 예선, UEFA컵 조별(2006-07·2007-08)은 유로파 조별, UEFA컵 3라운드·16강·8강과 유로파 32강은 유로파 토너먼트, 챔스 2차 조별(2001-02)은 조별, 그리스 슈퍼리그 플레이오프는 리그",
        f"두 경기 합산 기록 {V['NTIE']}개({V['NTIEG']}경기)는 합산 S로 계산함: UEFA 대회·잉글랜드 리그컵 준결승(2017-18까지)·그리스컵(2015-16 16강·8강, 발부에나·히바우두 선례)은 원정 다득점·연장. 다른 차전 스코어는 Transfermarkt 리포트",
        "시즌 구분: 레버쿠젠은 7월 10일 기준(2002.7.24·2004.7.21·7.28·2005.7.23 DFL-리가포칼이 새 시즌; 슈나이더·발라크 선례), 나머지 클럽은 기본 8월 1일. 클럽 구분(Transfermarkt 이적 기록): 2001.1.16 레버쿠젠, 2006.7.1 토트넘, 2008.9.1 맨유, 2012.8.31 풀럼, 2014.1.31 모나코, 2015.9.2 PAOK, 2017.8.23 케랄라. 경기 클럽과 경계 불일치 0",
        "같은 경기 동료 자료: " + ", ".join(f"{TEAMMATE[b]}(그 선수 도움→베르바토프 골 {v[0]}개·베르바토프 도움→그 선수 골 {v[1]}개)" for b, v in sorted(tmates.items(), key=lambda kv: -sum(kv[1]))) + "와 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명이 모두 같음. 상대 팀 선수 자료(아일톤·발라크·드로그바·제라드·고부·키슬링 등)와 골 순서도 맞음",
        "수상 기록은 Transfermarkt 업적 페이지 기준: 프리미어리그 2008-09·2010-11, 리그컵 2008(토트넘)·2010(맨유), 커뮤니티 실드 2010·2011, 클럽 월드컵 2008(출전 없음), 불가리아컵 1998-99. 준우승: 챔스 2001-02(레버쿠젠)·2008-09·2010-11(맨유, 2011 결승은 명단 밖), DFB-포칼 2001-02. 개인: 프리미어리그 득점왕 2010-11(20골, 테베스와 공동), DFB-포칼 득점왕 2001-02(6골), PFA 올해의 팀 2006-07·2010-11(영어 위키백과 PFA Team of the Year), 불가리아 올해의 선수 7회(2002·2004·2005·2007·2008·2009·2010). 분데스리가 준우승, 대표팀 기록은 뺌",
        f"은퇴(Transfermarkt 2018.4.1). 마지막 경기 {d_(last[0])} {ko(last[1])}전(인도 슈퍼리그, 63분 출전, 골·도움 없음)",
    ]
    return "\n".join(L)
