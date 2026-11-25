# 도움·골 판정 근거. build_pirlo.py가 exec로 읽음.
# A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 2014.8 이후 TM 도움 중 FotMob 경기 이벤트에 도움자가 없는 것은
# TM 외 출처 2곳(ESPN 경기 중계 기록 'Assisted by Andrea Pirlo' + FotMob 시즌 도움 합계가 TM과 같음)으로 확인.
# 2014.8 전 정상 유형(Pass·Cross·Corner·Free kick·Header·빈칸) TM 단독 도움은 선례대로 넣음.
_ESPN = "ESPN 경기 중계 기록(site.api.espn.com summary event {}) '{}' + FotMob 시즌 도움 합계({})가 TM과 같음"
A_CHECK = {
 "2478661|64": (True, _ESPN.format(403763, "Llorente header ... Assisted by Andrea Pirlo with a cross following a corner", "세리에A 2014-15 5")),
 "2478892|28": (True, _ESPN.format(403532, "Bonucci ... Assisted by Andrea Pirlo", "세리에A 2014-15 5")),
 "2478910|36": (True, _ESPN.format(403510, "Llorente header ... Assisted by Andrea Pirlo with a cross following a set piece situation", "세리에A 2014-15 5")),
 "2558250|80": (True, _ESPN.format(412278, "Villa ... Assisted by Andrea Pirlo", "MLS 2015 2")),
 "2558298|77": (True, _ESPN.format(412230, "Mullins header ... Assisted by Andrea Pirlo with a cross following a corner", "MLS 2015 2")),
 "2666913|41": (True, _ESPN.format(440874, "Villa ... Assisted by Andrea Pirlo with a cross following a corner", "MLS 2016 6")),
 "2666943|65": (True, _ESPN.format(440843, "McNamara ... Assisted by Andrea Pirlo", "MLS 2016 6")),
 "2666965|66": (True, _ESPN.format(440821, "Villa ... Assisted by Andrea Pirlo with a through ball", "MLS 2016 6")),
 "2667000|8": (True, _ESPN.format(440786, "Harrison ... Assisted by Andrea Pirlo following a corner", "MLS 2016 6")),
 "2667069|83": (True, _ESPN.format(440723, "Villa ... Assisted by Andrea Pirlo with a through ball", "MLS 2016 6")),
 "2667143|52": (True, _ESPN.format(440650, "Villa ... Assisted by Andrea Pirlo following a corner", "MLS 2016 6")),
 "2824702|19": (True, _ESPN.format(471439, "McNamara ... Assisted by Andrea Pirlo", "MLS 2017 1")),
}
ADD_A = []
# 골 제외: 2000.1.9 엘라스 베로나-레지나 38분. TM은 피를로 직접 프리킥 골, 이탈리아어 위키백과 시즌 기사 경기 상자·영어 위키백과
# 시즌 기사·statarea 상대 전적은 모두 베로나 골키퍼 프레이(Sébastien Frey)의 자책골(38분 aut.). 경기 단위 출처 다수를 따라 피를로 골에서 뺌
# (레지나 득점으로 스코어 진행에는 그대로 둠).
G_DROP = {"2211426|38": "상대 자책골(프레이) — 이탈리아어·영어 위키백과 레지나 1999-2000 시즌 기사 경기 상자, statarea; TM만 피를로 프리킥"}
