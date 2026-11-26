# 피르미누 수동 판정 표 (build_firmino.py 가 exec). 근거 원문은 judgments.md.
# 출처 약어: QSL = 카타르 스타스리그 공식 사이트(qsl.qa), 페닌슐라 = The Peninsula(thepeninsulaqatar.com), GT = 걸프 타임스(gulf-times.com),
# 구단 = 알사드 구단(al-saddclub.com), ESPN = ESPN 경기 문자 중계(site.api.espn.com summary), FFT = FourFourTwo, LFC = 리버풀 구단 경기 기사.

# ---- Transfermarkt에 없는 경기(경기 단위 출처 2곳 이상)
ADD_GAMES = [
    {"date": "2026-01-24", "opp": "Shabab Al-Ahli Club", "cid": "QUSS", "round": "Final", "min": 90, "est": 1,
     "why": "카타르-UAE 슈퍼컵 '슈퍼 실드'(카타르·UAE 리그 챔피언 단판) 알사드 3-2 샤바브 알아흘리(도하 자심 빈 하마드). QSL 경기 기사·페닌슐라 2026.1.25: 피르미누 55분 PK(0-1에서), 90+6분 결승골(2-2에서, 카마라 크로스). 영어 위키백과 2025-26 '기타' 1경기 2골. TM·FotMob에 경기 없음. 출전 분 자료 없음 → 90분 추정(아즈문 2025 챌린지 실드 선례)"},
    {"date": "2026-09-01", "opp": "Al-Gharafa SC", "cid": "QUC1", "round": "Semi-Finals", "min": 90, "est": 0,
     "why": "카타르컵 2026 준결승 알사드 2-1 알가라파(칼리파 국제경기장). FotMob 선수 경기 기록 90분·골 도움 없음, 영어 위키백과 2026-27 '기타' 1경기, QNA 2026.9.1 경기 기사. TM에는 경기 자체가 없음"},
]
ADD_E = [
    {"date": "2026-01-24", "opp": "Shabab Al-Ahli Club", "cid": "QUSS", "round": "Final", "type": "g", "minute": "55", "gf": 0, "ga": 1, "pk": 1,
     "why": "QSL·페닌슐라: 아피프가 얻은 PK를 피르미누가 성공(1-1)"},
    {"date": "2026-01-24", "opp": "Shabab Al-Ahli Club", "cid": "QUSS", "round": "Final", "type": "g", "minute": "90+6", "gf": 2, "ga": 2, "pk": 0,
     "why": "QSL '90+6분', 페닌슐라 '추가시간 6분째' 카마라 크로스 → 피르미누 결승골(3-2)"},
]

# ---- 도움 판정(키 = TM gameId|분). (True, 근거) = 넣음, (False, 근거) = 뺌. 규칙으로 빠지는 것(PK 유도·Shot on goal·자책골)은 빌드가 처리.
A_CHECK = {
    # 2014.8 이후 TM만(FotMob 도움자 없음) → 다른 출처 2곳 필요
    "2488534|23": (True, "ESPN 문자 중계 'Assisted by Roberto Firmino' · 호펜하임 구단 경기 기사(피르미누가 두 명을 제치고 왼쪽 쉬플로크에게 패스)"),
    "2488534|45+3": (False, "ESPN 문자 중계만(FotMob 이 경기 도움자 기록 없음, 다른 기사 확인 못 함)"),
    "2753645|50": (True, "ESPN 문자 중계 · FourFourTwo(쿠티뉴와 원투, 피르미누의 리턴 패스) · Sky Sports 경기 기사"),
    "2905729|21": (False, "ESPN만 피르미누, 유로스포츠 문자 중계는 피르미누 → 마네 백힐 → 엠레 잔(마지막 패스 마네)"),
    "3050331|80": (False, "FotMob 도움 없음, 유로스포츠만 '피르미누 내준 공 → 샤키리 슈팅이 바이에 맞고 굴절' — 출처 1곳"),
    "3192360|48": (True, "리버풀 구단 경기 기사·Goal.com(파비뉴 로빙 패스를 받은 피르미누가 옆으로 내줘 마네 마무리)"),
    "4168837|39": (False, "TM 유형 빈칸, FotMob·경기 기사 도움자 확인 못 함"),
    "4705848|90": (False, "QSL 경기 기사('피르미누 스루 패스')뿐 — 걸프 타임스는 같은 문장 재게재라 한 출처로 셈"),
    "4717303|18": (True, "QSL 'through pass from Roberto Firmino' · 페닌슐라 2025.12.30 'latching onto a through ball from Roberto Firmino'"),
    "4793129|6": (False, "QSL 경기 기사뿐(다른 기사 확인 못 함)"),
    "4793124|48": (True, "QSL 'through ball from Firmino' · 페닌슐라 2026.4.9 'latching onto a through ball from Roberto Firmino'"),
}

# ---- 순위 라벨 직접 지정(순위표 파일 밖)
FORCE = {
    "4850635": "J1 백년구상 리그 2026 서부 1위/10팀 (J1 100 Year Vision League West, 경기 날짜에 진행 중이던 특별 시즌 최종 순위)",
}
# 카타르 1부 2026-27 현재 순위(FotMob 리그 표 2026.11.26 받음, 10라운드 뒤)
QSL_NOW = {"Al-Rayyan SC": 1, "Al-Sadd SC": 2, "Al-Duhail SC": 3, "Al-Arabi SC": 4, "Al-Shamal SC": 5, "Al-Ahli SC": 6, "Lusail SC": 7,
           "Al-Gharafa SC": 8, "Al-Wakrah SC": 9, "Al-Shahania SC": 10, "Qatar SC": 11, "Al-Sailiya SC": 12}
