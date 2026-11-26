#!/usr/bin/env python3
"""K리그 공식 경기 기록(kleague.com 경기 센터 API) 받기: 전북(K05) 2014~2018 K리그1 일정 + 경기별 이벤트(득점·도움).
  python3 players/leejaesung/kleague_fetch.py        # kleague/schedule_<year>.json, kleague/match_<year>_<gameId>.json
요청 사이 1.2초. 이미 받은 파일은 건너뜀."""
import json, os, time, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "kleague")
os.makedirs(OUT, exist_ok=True)
def post(url, data, js=False):
    if js:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "Mozilla/5.0"})
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r: return json.loads(r.read().decode())
for y in range(2014, 2019):
    fn = os.path.join(OUT, f"schedule_{y}.json")
    if not os.path.exists(fn):
        L = []
        for m in range(1, 13):
            d = post("https://www.kleague.com/getScheduleList.do", {"year": str(y), "month": f"{m:02d}", "leagueId": "1", "teamId": "K05"}, js=True)
            L += [g for g in d["data"]["scheduleList"] if "K05" in (g["homeTeam"], g["awayTeam"])]
            time.sleep(1.2)
        json.dump(L, open(fn, "w"), ensure_ascii=False, indent=0)
    L = json.load(open(fn))
    print(y, len(L))
    for g in L:
        f2 = os.path.join(OUT, f"match_{y}_{g['gameId']}.json")
        if os.path.exists(f2): continue
        d = post("https://www.kleague.com/api/ddf/match/matchInfo.do", {"year": y, "meetSeq": g["meetSeq"], "gameId": g["gameId"]})
        json.dump(d, open(f2, "w"), ensure_ascii=False)
        time.sleep(1.2)
