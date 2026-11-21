# build_kewell.py가 exec. 통합표(elo/opponent_elo_by_team_season.csv)·raw/ranks.txt에 없는 팀-시즌의 순위 라벨(값은 tools/league_rank_apply.py).
# 근거는 judgments.md 4절. 키 = (상대 이름, 경기 날짜). 잉글랜드 풋볼 리그 1997~2004 순위는 영어 위키백과 시즌 문서 최종 순위표(raw/ranks_wiki.txt;
# Transfermarkt는 그 시즌 하부 리그 표를 주지 않음). 형식은 비두카 자료(챔피언십 2000-01 반즐리 등)와 같음.
_D1 = "Football League First Division"
MANUAL_LV = {
    ("Stoke City", "1997-10-15"): f"챔피언십 1997-98 23위/24팀 ({_D1})",
    ("Oxford United", "1998-01-03"): f"챔피언십 1997-98 12위/24팀 ({_D1})",
    ("Portsmouth FC", "1999-01-23"): f"챔피언십 1998-99 19위/24팀 ({_D1})",
    ("Manchester City", "2000-01-09"): f"챔피언십 1999-00 2위/24팀 ({_D1})",
    ("Crystal Palace", "2003-02-16"): f"챔피언십 2002-03 14위/24팀 ({_D1})",
}
NORANK = {}
NORANK_VAL = {}
