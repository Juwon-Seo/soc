#!/usr/bin/env python3
"""ESPN API(site.api.espn.com ecu.1 팀 2668 schedule·summary) 캐시 → espn_emelec_2010_2011.csv
   Transfermarkt에 없는 에멜렉 2010·2011 에콰도르 1부 리그 경기(선발/교체 시각·골 시각·골 순서)
   python3 espn_emelec_extract.py <캐시 폴더(sch_2010.json·sch_2011.json·sum_<id>.json)>"""
import json, sys, os, csv, datetime
SRC = sys.argv[1]
NAME = {"Deportivo Quito": "Deportivo Quito", "Liga de Quito": "LDU Quito", "Barcelona SC": "Barcelona SC Guayaquil", "El Nacional": "CD El Nacional",
        "Deportivo Cuenca": "Deportivo Cuenca", "Manta F.C.": "Manta FC", "Independiente Terán": "Independiente del Valle", "Olmedo": "CD Olmedo",
        "Espoli": "CD Espoli", "Imbabura": "Imbabura SC", "Liga de Loja": "LDU de Loja", "Macará": "CD Macará", "Universidad Católica (Quito)": "CD Universidad Católica"}
def m(x): return int(x.replace("'", "").split("+")[0]) if x else None
out = []
for s in (2010, 2011):
    for e in sorted(json.load(open(os.path.join(SRC, f"sch_{s}.json")))["events"], key=lambda e: e["date"]):
        d = json.load(open(os.path.join(SRC, f"sum_{e['id']}.json")))
        comp = d["header"]["competitions"][0]
        cs = {c["team"]["id"]: c for c in comp["competitors"]}
        opp = [c for k, c in cs.items() if k != "2668"][0]
        me = cs["2668"]
        utc = datetime.datetime.strptime(e["date"], "%Y-%m-%dT%H:%MZ")
        local = (utc - datetime.timedelta(hours=5)).strftime("%Y-%m-%d")   # Ecuador UTC-5 (경기장 모두 에콰도르)
        p = [x for r in d["rosters"] if r["team"]["id"] == "2668" for x in r.get("roster", []) if "Valencia" in x["athlete"]["displayName"] and "ner" in x["athlete"]["displayName"]]
        p = p[0] if p else None
        played = bool(p and (p.get("starter") or p.get("subbedIn")))
        sub = [m(x["clock"]["displayValue"]) for x in (p or {}).get("plays", []) if x.get("substitution")]
        if played:
            if p.get("starter"): start, end = 0, (sub[0] if p.get("subbedOut") and sub else 90)
            else: start, end = sub[0], (sub[1] if p.get("subbedOut") and len(sub) > 1 else 90)
            mins = end - start
        gh = ga = 0; goals = []
        for k in d.get("keyEvents", []):
            t = k["type"]["text"]
            if not (t.startswith("Goal") or t == "Penalty - Scored" or t == "Own Goal"): continue
            ours = k.get("team", {}).get("id") == "2668"
            who = [a["athlete"]["displayName"] for a in k.get("participants", [])]
            if ours and any("Valencia" in w and "ner" in w for w in who):
                goals.append(f"{k['clock']['displayValue']}@{gh}-{ga}{'P' if 'Penalty' in t else ''}")
            if ours: gh += 1
            else: ga += 1
        stage = "final" if e["id"] in ("306219", "306220", "327845", "327846") else "league"
        out.append({"season": s, "espn_id": e["id"], "date_local": local, "utc": e["date"], "opp_espn": opp["team"]["displayName"], "opp": NAME[opp["team"]["displayName"]],
                    "venue": "H" if me["homeAway"] == "home" else "A", "score_emelec_opp": f"{me.get('score')}-{opp.get('score')}", "stage": stage,
                    "played": int(played), "starter": int(bool(p and p.get("starter"))), "minutes": mins if played else "", "goals": " ".join(goals),
                    "espn_assists": int(sum(x["value"] for x in (p or {}).get("stats", []) if x["name"] == "goalAssists")), "check_goal_order": f"{gh}-{ga}"})
w = csv.DictWriter(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "espn_emelec_2010_2011.csv"), "w", encoding="utf-8", newline=""), fieldnames=list(out[0]))
w.writeheader(); w.writerows(out)
print(len(out), sum(r["played"] for r in out), sum(len(r["goals"].split()) for r in out))
