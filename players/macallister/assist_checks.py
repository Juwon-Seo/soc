# 도움 판정 근거: A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 모든 도움이 2014.8 이후 → TM 단독(FotMob 이벤트에 없음) 도움은
# TM 외 독립 출처 2곳이 있어야 넣음. FotMob 선수 경기 목록 도움 수는 FotMob 쪽 확인으로 봄(크로스·소보슬러이·귄도안 선례).
A_CHECK = {
 "3187031|90+5": (True, "TM + FotMob 선수 경기 목록(도움 1, 이벤트엔 도움자 없음) + ESPN 경기 기록(Salvio 'Assisted by Alexis Mac Allister')"),
 "3235459|11": (True, "TM + FotMob 선수 경기 목록(도움 1, 이벤트엔 도움자 없음) + ESPN 경기 기록(Ábila 'Assisted by Alexis Mac Allister with a through ball')"),
 "3282781|28": (True, "TM 단독(FotMob 자료 없음) + ESPN 경기 기록('De Rossi header … Assisted by Alexis Mac Allister with a cross following a corner') + 경기 기사(Trivela·El Gráfico: 맥알리스터의 코너킥을 데로시가 헤더)"),
}
ADD_A = []
# 넣지 않은 단일 출처 도움(judgments.md):
#  2017.10.27 아르세날 데 사란디전 37분 바탈리니 골: FotMob·ESPN(같은 Opta 자료)은 알렉시스, TM은 동생 프란시스(크로스) → 독립 출처 2곳 없음
#  2019.2.18 에스투디안테스전: FotMob 선수 경기 목록만 도움 1, FotMob 이벤트·TM·ESPN 모두 78분 오체 골 도움 없음 → 넣지 않음
