# build_diego.py 가 exec 로 읽는 부분: 상대 Elo (같은 경기 다른 선수 자료 → 직접 추정(MAN) → 팀×시즌 통합표 → 순위표+리그 모형)
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b == "hon.js" or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
STAGED = {}
for fn in [os.path.join(ROOT, "players", "candreva", "staged", "can.js")]:
    if os.path.exists(fn):
        P, oe, om = load_js(fn); STAGED["staged/" + os.path.basename(fn)] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "milan", "inter", "madrid", "moscow", "moskau", "paulista", "paulo", "ca", "cs", "club", "deportivo", "deportes", "universidad", "san", "santa",
        "borussia", "bayer", "vfl", "vfb", "tsv", "fsv", "munich", "munchen", "hamburger", "eintracht", "werder", "bsc", "hertha", "rb", "spor", "kulubu"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
SOUTH = {"BRA1", "BCP1", "BCPF", "BRCG", "BRCR", "BRCF", "BRC2", "BRC", "CLI", "CS", "RECO", "SCBR", "KLUB"}
def same_match(o, d, cid):
    if cid in SOUTH:   # 남미·국내 대회: 같은 이름 다른 팀 오인을 막으려 정확히 같은 팀 이름만(포를란·제 호베르투 선례)
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
def seas(lab):
    if "/" in lab:
        a, b = lab.split("/"); return f"20{a}-{b}"
    return lab
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], seas(p[1]))][key(p[4])] = (int(p[2]), int(p[3]), p[4])
RANK_FIX = {}    # (리그, 시즌, 팀 key) -> (순위, 팀 수, 근거) : Transfermarkt 표가 공식 최종 순위와 다른 경우(elo_fix 에서 채움)

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up((tab[a] + tab[b]) / 2) if True else None, True
INTERP_USED = set()

LG_PREFIX = {"L1": "분데스리가", "IT1": "세리에A", "ES1": "라리가", "TR1": "쉬페르리그", "PO1": "포르투갈 1부"}
def rank_model(lg, season, r, n):
    if lg == "BRA1":
        m = ents_map("브라질 세리에 A", season)
        if r in m: return m[r], f"브라질 세리에 A {season} {r}위"
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg in LG_PREFIX:
        m = ents_map(LG_PREFIX[lg], season)
        v, it = mid(m, r)
        if v is None: return None
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"{LG_PREFIX[lg]} {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
exec(open(os.path.join(HERE, "elo_man.py"), encoding="utf-8").read())

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
LG_OF_CLUB = {"720": "PO1", "86": "L1", "506": "IT1", "82": "L1", "13": "ES1", "36": "TR1"}
def opp_elo(o, d, cid, rnd=""):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); y = d[:4]
    if cid in SOUTH and cid != "KLUB":
        seasons = [y]
    elif cid in ("KLUB",):
        seasons = [y, eu(d)]
    elif cid in ("CL", "CLQ", "UEFA", "EL", "ELQ", "WEPO"):
        seasons = [eu(d), y, str(int(y) - 1)] if int(d[5:7]) < 7 else [eu(d), y]
    else:
        seasons = [eu(d)]
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    lgs = []
    if cid in SOUTH: lgs = [("BRA1", y)]
    else:
        g_club = next((g["club_id"] for g in GAMES if ldate(g) == d), None)
        if g_club in LG_OF_CLUB: lgs = [(LG_OF_CLUB[g_club], eu(d))]
    for lg, s in lgs:
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            if (lg, s, k) in RANK_FIX: r, n = RANK_FIX[(lg, s, k)][:2]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"
