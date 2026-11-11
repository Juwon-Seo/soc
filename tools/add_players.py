#!/usr/bin/env python3
"""새 선수를 src/index.html·src/data/hon.js 에 끼워 넣는 패치 (앵커 = 현재 마지막 선수)

  python3 tools/add_players.py <마지막 선수 프리셋 id> <players/a/integration.json> [<players/b/integration.json> ...]

integration.json 형식(선수별 판정 에이전트가 만듦):
{
  "preset": "klose", "name": "미로슬라프 클로제", "prefix": "KLO",
  "clubs": [ {"key": "homkl", "name": "FC 08 홈부르크", "short": "홈부르크", "years": "1998~1999", "until": "1999-07-01"}, ...,
             {"key": "lazkl", "name": "라치오", "short": "라치오", "years": "2011~2016", "until": null} ],
  "season": {"calendar": ["torin"], "jul10": [], "jul1": []},  # seasonOf 예외(없으면 빈 목록)
  "pos": "CF", "flag": "DE", "retired": true,
  "color_light": "#xxxxxx", "color_dark": "#xxxxxx",   # 비우면 이 스크립트가 고름
  "hon": { "t": {...}, "o": [...], "a": {...} }
}
앵커마다 정확히 지정 횟수만큼 있는지 검사하고(rep), 하나라도 어긋나면 아무것도 쓰지 않는다.
"""
import json, re, sys, os, colorsys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "src", "index.html")
HON = os.path.join(ROOT, "src", "data", "hon.js")


def rep(s, old, new, n=1):
    c = s.count(old)
    if c != n:
        sys.exit(f"앵커 개수 불일치({c}≠{n}): {old[:90]!r}")
    return s.replace(old, new)


def hexrgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def far_color(existing, light):
    """기존 색과 RGB 거리가 가장 먼 색(채도 높은 후보 중)"""
    ex = [hexrgb(c) for c in existing]
    best, bd = None, -1
    for hi in range(72):
        for sat, val in ((0.85, 0.75), (0.7, 0.9), (0.95, 0.55)) if light else ((0.55, 0.95), (0.75, 0.9), (0.35, 1.0)):
            r, g, b = colorsys.hsv_to_rgb(hi / 72, sat, val)
            d = min(((r - x) ** 2 + (g - y) ** 2 + (b - z) ** 2) for x, y, z in ex)
            if d > bd:
                bd, best = d, (r, g, b)
    return "#%02x%02x%02x" % tuple(round(v * 255) for v in best)


def main():
    # 안전장치: 정본 저장소(/home/user/soc)는 ADD_PLAYERS_REAL=1 일 때만 고친다(검증은 복사본에서 — 판정 에이전트가 실수로 원본을 고친 일이 두 번 있었음)
    if os.path.realpath(ROOT) == "/home/user/soc" and os.environ.get("ADD_PLAYERS_REAL") != "1":
        sys.exit("정본 저장소에는 ADD_PLAYERS_REAL=1 python3 tools/add_players.py … 로만 실행합니다(검증은 복사본에서)")
    last = sys.argv[1]
    specs = [json.load(open(p, encoding="utf-8")) for p in sys.argv[2:]]
    s = open(IDX, encoding="utf-8").read()
    hon = open(HON, encoding="utf-8").read()

    # 마지막 선수 정보 읽기
    m = re.search(r'(\b' + last + r':\{name:"[^"]+",ver:pver\(([A-Z]+)_E,[A-Z]+_M\),entries:mk\([A-Z]+_E\),matches:mkM\([A-Z]+_M\),note:[A-Z]+_NOTE\})\}', s)
    if not m:
        sys.exit("마지막 선수 PRESETS 항목을 못 찾음")
    lp = m.group(2)
    lfile = lp.lower()
    pcl = re.search(r'\b' + last + r':\[("[a-z0-9]+"(?:,"[a-z0-9]+")*)\]', s).group(1)
    lkeys = [k.strip('"') for k in pcl.split(",")]
    lastkey = lkeys[-1]
    lfn = re.search(r'p\.preset==="' + last + r'"\?([a-zA-Z]+)\(d\):', s).group(1)
    n_now = int(re.search(r'return \(i%(\d+)\)\+1\}', s).group(1))

    tag_anchor = f'<script src="data/{lfile}.js"></script>'
    tags, presets, autoadd, pclubs, clubs2, fns, pcl_tern, cl_add, pos_add, flag_add = [], [], [], [], [], [], [], [], [], []
    for sp in specs:
        P, pid = sp["prefix"], sp["preset"]
        if not os.path.exists(os.path.join(ROOT, "src", "data", P.lower() + ".js")):
            sys.exit(f"데이터 파일 없음: src/data/{P.lower()}.js")
        tags.append(f'<script src="data/{P.lower()}.js"></script>')
        presets.append(f',{pid}:{{name:"{sp["name"]}",ver:pver({P}_E,{P}_M),entries:mk({P}_E),matches:mkM({P}_M),note:{P}_NOTE}}')
        autoadd.append(f'if(!st.players.some(p=>p.preset==="{pid}")){{st.players.push(fromPreset("{pid}"))}}')
        ks = list(dict.fromkeys(c["key"] for c in sp["clubs"]))  # 다시 돌아온 클럽은 같은 키(임모빌레 torim 선례)
        uniq = []
        for c in sp["clubs"]:
            u = next((x for x in uniq if x["key"] == c["key"]), None)
            if u: u["years"] += ", " + c["years"]
            else: uniq.append(dict(c))
        for k in ks:
            if re.search(r'[,{]' + k + r':\[', s) or re.search(r'"' + k + r'"', s):
                sys.exit(f"클럽 키가 이미 있음: {k}")
        pclubs.append(f'{pid}:[' + ",".join(f'"{k}"' for k in ks) + '],')
        clubs2.append("".join(f'{c["key"]}:["{c["name"]}","{c["years"]}"],' for c in uniq))
        fn = P[0] + P[1:].lower() + "Club"
        fn = P.lower() + "Club"
        body, cl = "", sp["clubs"]
        for c in cl[:-1]:
            body += f'd<"{c["until"]}"?"{c["key"]}":'
        body += f'"{cl[-1]["key"]}"'
        fns.append(f'\nfunction {fn}(d){{d=d||"";if(!d)return "";return {body}}}')
        pcl_tern.append(f'p.preset==="{pid}"?{fn}(d):')
        cl_add.append("".join(f'{c["key"]}:"{c["short"]}",' for c in uniq))
        pos_add.append(f',{pid}:"{sp["pos"]}"')
        flag_add.append(f',{pid}:"{sp["flag"]}"')

    s = rep(s, tag_anchor, tag_anchor + "".join("\n" + t for t in tags))
    s = rep(s, m.group(1) + "}", m.group(1) + "".join(presets) + "}")
    aa = f'if(!st.players.some(p=>p.preset==="{last}")){{st.players.push(fromPreset("{last}"))}}'
    s = rep(s, aa, aa + "".join(autoadd))
    s = rep(s, f'{last}:[{pcl}],', f'{last}:[{pcl}],' + "".join(pclubs))
    c2 = re.search(r'\b' + lastkey + r':\["[^"]*","[^"]*"\],', s).group(0)
    s = rep(s, c2, c2 + "".join(clubs2))
    fdef = re.search(r'function ' + lfn + r'\(d\)\{[^\n]*\}', s).group(0)
    s = rep(s, fdef, fdef + "".join(fns))
    s = rep(s, f'p.preset==="{last}"?{lfn}(d):', f'p.preset==="{last}"?{lfn}(d):' + "".join(pcl_tern))
    cln = re.search(r'\b' + lastkey + r':"[^"]*",', s).group(0)
    s = rep(s, cln, cln + "".join(cl_add), 2)
    pos = re.search(r'\b' + last + r':"(CF|SS|LW|RW|LM|RM|AM|CM|DM)"\}', s).group(0)
    s = rep(s, pos, pos[:-1] + "".join(pos_add) + "}")
    flag = re.search(r'\b' + last + r':"([A-Z]{2,3})"\}', s).group(0)
    s = rep(s, flag, flag[:-1] + "".join(flag_add) + "}")
    # seasonOf
    for sp in specs:
        j1 = sp.get("season", {}).get("jul1", [])
        if j1:  # 7월 1일 기준(우크라이나 리그·1995 인터토토처럼 7월 초 경기가 새 시즌) — kobvl 줄 뒤에 분기 하나
            s = rep(s, 'if(club==="kobvl")return "2019";', 'if(club==="kobvl")return "2019";if(' + "||".join(f'club==="{k}"' for k in j1) + '){const s=d.slice(5)>="07-01"?y:y-1;return s+"-"+String(s+1).slice(2)}')
        cal = sp.get("season", {}).get("calendar", [])
        if cal:
            s = rep(s, ')return String(y);if(club==="kobvl")', "".join(f'||club==="{k}"' for k in cal) + ')return String(y);if(club==="kobvl")')
        j10 = sp.get("season", {}).get("jul10", [])
        if j10:  # 키 여러 개를 한 번에(앵커가 한 번 바뀌면 다시 못 찾음)
            mj = re.findall(r'\|\|club==="[a-z0-9]+"\)\{const s=d\.slice\(5\)>="07-10"', s)  # 7월 10일 목록의 끝(마지막 키는 바뀜)
            if len(mj) != 1:
                sys.exit(f"7월 10일 목록 앵커가 {len(mj)}개")
            s = rep(s, mj[0], mj[0][:-len('){const s=d.slice(5)>="07-10"')] + "".join(f'||club==="{k}"' for k in j10) + '){const s=d.slice(5)>="07-10"')
    ret = [sp["preset"] for sp in specs if sp.get("retired")]
    if ret:
        rm = re.search(r'RETIRED=new Set\(\[([^\]]*)\]\)', s)
        s = rep(s, rm.group(0), 'RETIRED=new Set([' + rm.group(1) + "".join(f',"{p}"' for p in ret) + '])')
    # 색
    css_light = re.search(r'--s' + str(n_now) + r':(#[0-9a-f]{6})\}', s)
    light_ex = re.findall(r'--s\d+:(#[0-9a-f]{6})', s[:css_light.end()])
    dark_ex = re.findall(r'--s\d+:(#[0-9a-f]{6})', s[css_light.end():])
    dark_last = re.findall(r'--s' + str(n_now) + r':(#[0-9a-f]{6})\}', s)
    if len(dark_last) != 3:
        sys.exit(f"--s{n_now} 색 정의가 3곳이 아님: {len(dark_last)}")
    lt, dk = "", ""
    for i, sp in enumerate(specs):
        n = n_now + 1 + i
        cl_ = sp.get("color_light") or far_color(light_ex, True); light_ex.append(cl_)
        cd_ = sp.get("color_dark") or far_color(dark_ex, False); dark_ex.append(cd_)
        sp["_cl"], sp["_cd"] = cl_, cd_
        lt += f';--s{n}:{cl_}'; dk += f';--s{n}:{cd_}'
    s = rep(s, f'--s{n_now}:{dark_last[0]}}}', f'--s{n_now}:{dark_last[0]}{lt}}}')
    s = rep(s, f'--s{n_now}:{dark_last[1]}}}', f'--s{n_now}:{dark_last[1]}{dk}}}', 2)
    s = rep(s, f'return (i%{n_now})+1}}', f'return (i%{n_now + len(specs)})+1}}')
    # 우승·수상
    for sp in specs:
        if f'"{sp["preset"]}":' in hon:
            sys.exit("hon.js 에 이미 있음: " + sp["preset"])
        hon = rep(hon, 'const HON_DATA={', 'const HON_DATA={' + json.dumps(sp["preset"], ensure_ascii=False) + ':' + json.dumps(sp["hon"], ensure_ascii=False, separators=(",", ":")) + ',')
    open(IDX, "w", encoding="utf-8").write(s)
    open(HON, "w", encoding="utf-8").write(hon)
    for sp in specs:
        print(sp["preset"], "추가 · 색", sp["_cl"], sp["_cd"])


if __name__ == "__main__":
    main()
