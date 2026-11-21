# build_viduka.py가 exec. 통합표(elo/opponent_elo_by_team_season.csv)·raw/ranks.txt에 없는 팀-시즌의 순위 라벨(값은 tools/league_rank_apply.py).
# 근거는 judgments.md 4절. 키 = (상대 이름, 경기 날짜).
_HNL = "Prva HNL, 플레이오프·스플릿 뒤 최종 순위"
MANUAL_LV = {
    # 호주 NSL(정규 리그 최종 순위표; 결선 결과로 순위를 바꾸지 않음): RSSSF aus94·aus95 Final Table = 위키백과 1993–94·1994–95 National Soccer League
    ("South Melbourne FC", "1994-04-17"): "호주 1부 1993-94 2위/14팀 (National Soccer League)",
    ("Heidelberg United", "1994-10-16"): "호주 1부 1994-95 13위/13팀 (National Soccer League)",
    ("South Melbourne FC", "1995-04-30"): "호주 1부 1994-95 6위/13팀 (National Soccer League)",
    # 크로아티아 1. HNL(위키백과 시즌 문서; 1995-96·1997-98·1998-99는 1단계 뒤 우승·강등 그룹으로 나뉜 최종 순위)
    ("NK Varteks Varazdin", "1996-05-01"): f"크로아티아 1부 1995-96 3위/12팀 ({_HNL})",        # 우승 그룹 3위
    ("NK Zadar", "1996-04-03"): "크로아티아 2부 1995-96 3위/10팀 (Prva B HNL, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",  # B HNL 3위 → 하위 플레이오프 그룹 1위(상위 2팀은 A 플레이오프)
    ("NK Osijek", "1997-04-09"): "크로아티아 1부 1996-97 8위/16팀 (Prva HNL)",
    ("NK Zagreb", "1997-05-29"): "크로아티아 1부 1996-97 5위/16팀 (Prva HNL)",
    ("NK Zagreb", "1998-04-01"): f"크로아티아 1부 1997-98 5위/12팀 ({_HNL})",                 # 우승 그룹 5위
    ("NK Varteks Varazdin", "1998-05-14"): f"크로아티아 1부 1997-98 10위/12팀 ({_HNL})",       # 강등 그룹(7~12위) 10위
    ("NK Mladost 127", "1998-09-11"): f"크로아티아 1부 1998-99 12위/12팀 ({_HNL})",            # 강등 그룹 최하위
    # 세르비아(유고) 1996-97: 7.30 챔스 예선 = 막 끝난 시즌. 1부 IA 12팀(33경기) 파르티잔 우승(위키백과 1996–97 First League of FR Yugoslavia, 84점)
    ("FK Partizan Belgrade", "1997-07-30"): "세르비아 1부 1996-97 1위/12팀 (First League of FR Yugoslavia)",
    # 웨일스 1998-99(8.12 UEFA컵 예선 = 막 끝난 시즌, 1999-2000 리그는 8월 하순 개막): RSSSF wal99 최종 순위 3위/17팀(애버리스트위스와 57점 동률, 득실 +29 대 +11)
    ("Cwmbran Town", "1999-08-12"): "웨일스 1부 1998-99 3위/17팀 (League of Wales)",
    # 스코틀랜드 2부(Scottish First Division): 위키백과 1998–99·1999–2000 Scottish First Division
    ("Greenock Morton FC", "1999-03-08"): "스코틀랜드 2부 1998-99 6위/10팀 (Scottish First Division, 리그 수준 추정)",
    ("Ayr United FC", "1999-10-13"): "스코틀랜드 2부 1999-00 7위/10팀 (Scottish First Division, 리그 수준 추정)",
    # 잉글랜드 하부(위키백과 시즌 문서 최종 순위표, raw/ranks_wiki.txt)
    ("Barnsley FC", "2001-01-06"): "챔피언십 2000-01 16위/24팀 (Football League First Division)",
    ("Cardiff City", "2002-01-06"): "잉글랜드 3부 2001-02 4위/24팀 (Football League Second Division, 리그 수준 추정)",
    ("Scunthorpe United", "2003-01-04"): "잉글랜드 4부 2002-03 5위/24팀 (Football League Third Division, 리그 수준 추정)",
    ("Gillingham FC", "2003-02-04"): "챔피언십 2002-03 11위/24팀 (Football League First Division)",
    ("Nuneaton Town", "2006-01-17"): "잉글랜드 6부 2005-06 3위/22팀 (Conference North, 리그 수준 추정)",
}
# 순위를 정할 수 없는 상대: 그 단계 기준점(tools/league_rank_apply.py base())
NORANK = {
    ("NK Dugo Selo", "1998-09-08"): "크로아티아 4부 1998-99 순위 없음 (NK Dugo Selo, 위키백과 시즌 문서의 4부 표기; 리그 수준 추정)",
}
NORANK_VAL = {lv: int(round(RA["base"]("Croatia", 4, 1999))) for lv in NORANK.values()}
