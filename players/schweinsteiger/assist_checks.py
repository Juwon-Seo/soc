# 도움·골 판정 근거(build_schweinsteiger.py가 exec로 읽음).
# A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 2014.8 이후 TM 단독 도움은 TM 외 독립 출처 2곳이 있어야 넣음(FotMob·구단/리그 공식 기록·경기 기사).
A_CHECK = {
 # 2015.8.26 챔스 PO 2차전 클루브 브뤼허 원정 63분 에레라 골(TM 'Pass', FotMob 이벤트 도움자 없음)
 "2613774|63": (True, "TM 단독(FotMob 도움자 없음) → Sky Sports 경기 기사('Schweinsteiger got the direct assist he deserved when his through-ball put Herrera into acres of space') + Bleacher Report 경기 기사('Herrera got the fourth after a clever, defence-splitting pass from Schweinsteiger') 2곳 확인"),
 # 2018.7.18 US 오픈컵 8강 루이빌 시티전 32분 카타이 골(TM 'Pass', FotMob 이벤트 도움자 없음)
 "3054339|32": (True, "TM 단독(FotMob 도움자 없음) → 시카고 파이어 구단 공식 경기 기록('CHI – Aleksandar Katai (Bastian Schweinsteiger) 32’') + USL 챔피언십 공식 기사(같은 득점 기록) + MLSsoccer.com 경기 기사('a feed for Bastian Schweinsteiger, who set up Katai') 확인"),
}
GOAL_FIX = {}
# FotMob에만 있는 도움: 없음(수집 자료에 FotMob 단독 도움 없음)
ADD_A = []
