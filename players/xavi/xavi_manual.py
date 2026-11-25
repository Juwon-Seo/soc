# 사비 수동 판정 표 (build_xavi.py 가 exec). 근거 원문은 judgments.md.
# 출처 약어: 구단 = 알사드 구단 기사 보관소(archive.al-saddclub.com, 영어·아랍어 경기 기사·경기 카드), GT = 걸프 타임스(gulf-times.com),
# 페닌슐라 = The Peninsula(thepeninsulaqatar.com), QT = 카타르 트리뷴(qatar-tribune.com), QSL = 카타르 스타스리그 공식 사이트(qsl.qa),
# ESPN = ESPN 경기 문자 중계(site.api.espn.com summary), QNA = 카타르 통신.

# ---- TM·FotMob에 없는 알사드 경기(위키백과 117경기 = TM 106 + 아래 11). 출전은 경기 단위 출처로 확인한 것만, 분은 선발·교체 없음 → 90 추정.
ADD_GAMES = [
    {"date": "2016-04-25", "opp": "El-Jaish SC", "cid": "QUC1", "round": "Semi-Finals", "min": 90,
     "why": "카타르컵(왕세자컵) 준결승 2-3 패. GT 2016.4.25 'captain Xavi'(65분 패스·88분 프리킥) — TM·FotMob에 경기 없음"},
    {"date": "2016-05-07", "opp": "Al-Gharafa SC", "cid": "QEC1", "round": "Quarter-Finals", "min": 90,
     "why": "에미르컵 8강 3-2 승. 구단 경기 카드 선발(교체 없음), GT 9분 사비 프리킥 → 분제자 헤더"},
    {"date": "2016-05-13", "opp": "Al-Rayyan SC", "cid": "QEC1", "round": "Semi-Finals", "min": 90,
     "why": "에미르컵 준결승 3-2 승. 구단 경기 카드 선발(교체 없음), GT 20분 사비 패스 → 하이도스"},
    {"date": "2016-05-20", "opp": "Lekhwiya SC", "cid": "QEC1", "round": "Final", "min": 90,
     "why": "에미르컵 결승 2-2, 승부차기 2-4 패. 구단 경기 카드 선발(교체 없음)·승부차기 첫 키커 성공(구단·GT·QSL). 연장 없이 바로 승부차기(QSL·GT·구단)"},
    {"date": "2017-04-20", "opp": "Al-Rayyan SC", "cid": "QUC1", "round": "Semi-Finals", "min": 90,
     "why": "카타르컵 준결승 3-2 승. 구단 경기 카드 선발(교체 없음)"},
    {"date": "2017-05-05", "opp": "Al-Kharaitiyat SC", "cid": "QEC1", "round": "Quarter-Finals", "min": 90,
     "why": "에미르컵 8강 4-1 승. 구단 경기 카드(영어·아랍어) 선발(교체 없음)"},
    {"date": "2017-05-14", "opp": "El-Jaish SC", "cid": "QEC1", "round": "Semi-Finals", "min": 90,
     "why": "에미르컵 준결승 2-0 승. 구단 경기 카드 선발(교체 없음), 페닌슐라 2017.5.14 '사비가 공격 대부분을 설계'"},
    {"date": "2017-05-19", "opp": "Al-Rayyan SC", "cid": "QEC1", "round": "Final", "min": 90,
     "why": "에미르컵 결승 2-1 승. 구단 경기 카드 선발(교체 없음), QT·GT·QNA 90+1분 사비 패스 → 하므룬 결승골"},
    {"date": "2017-09-16", "opp": "Al-Markhiya SC", "cid": "QSL", "round": "1. Matchday", "min": 90,
     "why": "리그 1라운드. 경기장 결과 알마르키야 2-1(사비 20분 프리킥 골), 카타르축구협회 징계위가 출전 자격 없는 선수 기용으로 알사드 3-0 승 처리(QSL·페닌슐라 2017.9.22 '이전 결과는 무효'). TM은 몰수 경기라 출전 'not in squad'. 구단 경기 카드 선발(교체 없음) → 출전 남기고 골은 무효 처리라 뺌"},
    {"date": "2018-11-16", "opp": "Al-Sailiya SC", "cid": "QSCP", "round": "Group C", "min": 90,
     "why": "QSL컵(스타스컵) 조별 3-3. 구단 경기 카드 선발(교체 없음). 5분 하메드 이스마일 골은 사비 패스 → 알리 아사드 슈팅이 막힌 리바운드라 도움 아님"},
    {"date": "2019-05-11", "opp": "Al-Rayyan SC", "cid": "QEC1", "round": "Semi-Finals", "min": 90,
     "why": "에미르컵 준결승 2-0 승. 구단 경기 카드(영어·아랍어) 선발(교체 없음), QT 2019.5.13 '사비의 알사드 경기장 마지막 경기'. TM 'not in squad'와 충돌 → 서로 다른 두 출처를 따름(라울 2014 에미르컵 결승 선례)"},
]

# ---- 위 경기의 도움(2014.8 이후라 서로 다른 출처 2곳 이상)
ADD_E = [
    {"date": "2016-05-07", "opp": "Al-Gharafa SC", "cid": "QEC1", "round": "Quarter-Finals", "minute": "9", "gf": 0, "ga": 0, "scorer": "Baghdad Bounedjah",
     "why": "GT 2016.5.7 '9분 사비 프리킥을 분제자가 헤더' · 구단 아랍어 기사 '9분 사비 크로스 → 분제자 헤더'"},
    {"date": "2016-05-13", "opp": "Al-Rayyan SC", "cid": "QEC1", "round": "Semi-Finals", "minute": "20", "gf": 1, "ga": 1, "scorer": "Hassan Al-Haydos",
     "why": "GT 2016.5.13 '사비 패스를 받아 하이도스 골(19분 PK 동점 뒤)' · 구단 아랍어 기사 '20분 사비의 멋진 패스 → 하이도스'"},
    {"date": "2016-05-20", "opp": "Lekhwiya SC", "cid": "QEC1", "round": "Final", "minute": "67", "gf": 1, "ga": 0, "scorer": "Abdelkarim Hassan",
     "why": "QSL 'A well placed freekick from Xavi found the head of Hassan' · 구단 아랍어 기사 '사비 크로스 → 압델카림 헤더'(GT는 키커 이름 없이 프리킥 헤더)"},
    {"date": "2017-05-19", "opp": "Al-Rayyan SC", "cid": "QEC1", "round": "Final", "minute": "90+1", "gf": 1, "ga": 1, "scorer": "Jugurtha Hamroun",
     "why": "QT 'a brilliant Xavi pass found Hamroun' · QNA 'Xavi found Hamroun with a killer pass' · GT 'laid down a great through pass' · 구단 영어 기사"},
]

# ---- 도움 판정: key = "TM gameId|TM 분" → (넣음?, 근거)
A_CHECK = {
    # 2014.8 전(TM 단일 출처 허용) 중 출처 차이를 확인한 것
    "1072026|73": (True, "2011.1.12 코파 8강 베티스 73분 메시: FotMob은 이니에스타 도움, AP(폭스스포츠) 'Messi was sent through down the middle by Xavi'·messivsronaldo 경기 기록 사비 도움 → TM 유지(이니에스타 자료에도 이 골 도움 없음)"),
    # 바르셀로나 2014-15
    "2532388|88": (True, "2015.3.4 코파 준결승 비야레알 88분 네이마르 헤더: FotMob 도움자 없음, ESPN 'Assisted by Xavi with a cross'·Sports Mole 문자 중계 'Xavi delivers an excellent cross into Neymar'·블리처 리포트 'Xavi curled an inch-perfect cross' → 넣음"),
    # 알사드(카타르 리그·컵은 FotMob 도움 칸이 비어 있음 → 서로 다른 출처 2곳)
    "2653799|58": (True, "구단 'Belhadj converting a Xavi pass' · QSL 'with a Xavi assist Belhadj tapped in'"),
    "2760688|25": (True, "구단 'picked up a pass from Xavi' · 페닌슐라 'pin-point pass from Xavi'"),
    "2768258|9": (True, "구단 'Kasola met Xavi's cross with a header' · GT '9분 정확한 사비 프리킥을 카솔라가 헤더'"),
    "2794263|85": (True, "구단 'put through by Xavi' · 페닌슐라(QSL 같은 글) 'Captain Xavi won the ball in midfield and calmly put through Bounjah'"),
    "2803561|66": (True, "구단 'Hamroun picked up a through pass from Xavi' · 페닌슐라 'Wolves captain Xavi picked out ... Hamroun who gracefully chipped'"),
    "2805384|24": (True, "구단 'headed in a free kick from Xavi' · GT(QSL 같은 글) 'Xavi's free kick was headed into the goal by Morteza'"),
    "2805384|50": (True, "구단 'after being put through by Xavi' · GT 'off an assist by Xavi'"),
    "2805396|6": (True, "구단 'Xavi sent in a corner ... Pouraliganji headed in' · GT 'from the resulting corner, Xavi found the head of ... Pouraliganji'"),
    "2817771|66": (False, "2017.1.27 알가라파 66분 산하지: 구단 영어·아랍어 기사 모두 산하지 단독 돌파(사비 관여 없음), GT도 사비 도움 언급 없음 → 확인 못 함"),
    "2826155|5": (True, "구단 'the ball fell to the feet of Xavi who squared it for Pouraliganji' · GT(QSL 같은 글) 'Xavi squared the ball to ... Morteza'"),
    "2826155|79": (False, "2017.2.16 알아라비 79분 분제자: 구단 영어·아랍어 기사 '박스 밖 강한 슈팅'(사비 언급 없음) → 확인 못 함"),
    "2827838|20": (False, "2017.2.24 알코르 20분 하이도스: 구단 'Xavi set up Al-Haydos'뿐, 페닌슐라는 첫 골을 칼판 이브라힘으로 적고 사비 도움 언급 없음 → 단일 출처"),
    "2827838|90+3": (False, "2017.2.24 알코르 90+3분 산하지: 구단 'after a pass from Xavi'뿐(페닌슐라 언급 없음) → 단일 출처"),
    "3677214|20": (True, "셰이크 자심컵 결승: 구단·QT 'Xavi Hernandez proving the assist'·GT 'it was Xavi who was the provider'"),
    "3677214|66": (True, "셰이크 자심컵 결승: 구단 'another assist from Xavi'·QT 'a pinpoint pass from Xavi'·GT 'Xavi once again providing the assist'"),
    "2933440|56": (True, "구단 'After picking up a pass from Xavi in the box' · QSL 경기 기사 'Xavi played a beautiful through ball to Boualem Khoukhi'"),
    "2977260|84": (True, "구단 'converting a cross by Xavi' · 페닌슐라 'Xavi produced a long ball towards Jan Pour who headed home'"),
    "2977277|40": (True, "구단 'Xavi sent in a free-kick ... headed in by Pedro Miguel' · QSL 경기 기사 'heading home a free-kick taken by Xavi Hernandez'"),
    "2977277|81": (False, "2017.12.7 알카라이티야트 81분 하이도스: 구단 영어·아랍어 기사 '왼쪽에서 파고들어 슈팅'(사비 언급 없음) → 확인 못 함"),
    "2988859|38": (True, "구단 'After picking up a pass from Xavi, Hamroun' · QSL 'His lofted pass was chased down by Hamroun'"),
    "2988875|44": (True, "구단 'Xavi's through ball was picked up by Hamroun' · QSL 'trapped an inch-perfect pass by Xavi'"),
    "2979546|79": (True, "AFC 챔스 알와슬: FotMob 이벤트 도움 없음(골 시각 90분으로 다르게 적음), ESPN 79분 'Assisted by Xavi' · 구단 'After a pass from Xavi'"),
    "2979547|51": (True, "AFC 챔스 페르세폴리스: ESPN 'Assisted by Xavi' · 구단 'Xavi who set up the striker with a magical pass'"),
    "3033940|2": (True, "AFC 챔스 16강 알아흘리: ESPN 3분 'Assisted by Xavi with a through ball' · 구단 'After a great exchange of passes with Xavi'"),
    "3098105|25": (False, "2018.8.12 알아라비 25분 아피프: QSL '사비 코너킥 뒤 아흐메드 이브라힘의 잘못된 걷어내기'를 아피프가 넣음(흘러나온 공) → 도움 아님"),
    "3098105|50": (True, "구단 'repeating the trick via Xavi's delivery' · QSL 'Hamed Ismail and Xavi gave the crosses in that order'"),
    "3044699|65": (True, "AFC 챔스 8강 에스테그랄: ESPN 'Assisted by Xavi with a through ball' · 구단 'latched onto Xavi's flicked through ball'"),
    "3108387|3": (True, "구단 'Xavi sent in a cross from the left and Bounedjah powered home a header' · QSL 'a header following an assist from captain Xavi Hernandez'"),
    "3108387|14": (True, "구단 'Boualem then got to the end of Xavi's corner' · QSL 'Khoukhi had headed in a Xavi corner kick'"),
    "3108399|70": (True, "QSL 'a snap-header off a Xavi free-kick' · 구단 아랍어 기사 '70분 사비 크로스 → 분제자 헤더'"),
    "3160137|87": (True, "AFC 챔스 팍타코르: ESPN 'Assisted by Xavi' · 구단 'Xavi pounced on a mistake ... played the ball across to Bounedjah'"),
}

# ---- 순위표 밖 라벨: TM 2017-18 카타르 순위표는 움살랄 4위·알가라파 5위이나 기존 자료(움살랄 5위)·위키백과 순위표(알가라파 승점 4위)를 따름
man("Al-Gharafa SC", "2017-18", "카타르 1부 2017-18 4위/12팀 (Qatar Stars League)")
