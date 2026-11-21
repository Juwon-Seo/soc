# 직접 정한 상대 Elo(build_mandzukic.py가 exec로 읽음). 순위는 영어 위키백과 최종 순위표로 확인(judgments.md 5절).
# 리그 시즌 수준 모형이 있는 나라(v1.216~v1.222: 아제르바이잔·체코·스코틀랜드, v1.217: 이란·카타르)는 그 시즌 목표 평균 + 흩어짐 × 순위 곡선.
def ov(o, s, cn, r, n, y_end, lab): man(o, s, other_v(cn, r, n, y_end), lab)
def wv(o, s, cc, r, n, wkey, lab): man(o, s, half_up(WM["평균"][f"{cc}|{wkey}"] + WM["흩어짐"][cc] * cv(r, n)), lab)
ov("Khazar Lankaran", "2007-08", "Azerbaijan", 4, 14, 2008, "아제르바이잔 2007-08 4위/14팀")
ov("AC Sparta Praha", "2008-09", "Czechia", 2, 16, 2009, "체코 2008-09 2위")
ov("Heart of Midlothian FC", "2009-10", "Scotland", 6, 12, 2010, "스코틀랜드 2009-10 6위")
wv("Persepolis FC", "2019-20", "IRN", 1, 16, "2020", "이란 1부 2019-20 1위")
wv("Al-Sailiya SC", "2019-20", "QAT", 5, 12, "2020", "카타르 2019-20 5위")
# 모형 밖 리그(추정)
# 아르메니아: 리그 시즌 수준 도구에 없음 → UEFA 계수로 같은 식의 목표 평균(2009·2010 시즌 끝 연도 평균 1317)에 아제르바이잔·슬로베니아 흩어짐(36) × 1위 곡선
def _arm_v():
    G_ = {"__file__": os.path.join(ROOT, "tools", "league_era_normalize.py"), "__name__": "x"}
    src = open(G_["__file__"], encoding="utf-8").read().replace("if '--apply' in sys.argv:", "if False:")
    argv = sys.argv; sys.argv = ["x"]
    with contextlib.redirect_stdout(io.StringIO()): exec(compile(src, "era", "exec"), G_)
    sys.argv = argv
    base = (G_["otarget_raw"]("Armenia", 2009) + G_["otarget_raw"]("Armenia", 2010)) / 2
    return half_up(base + 36 * cv(1, 8)), round(base)
_pv, _pb = _arm_v()
man("FC Pyunik Yerevan", "2009", _pv, f"아르메니아 2009 1위/8팀 (추정, 아르메니아 UEFA 국가 계수로 구한 리그 평균 {_pb} + 아제르바이잔·슬로베니아 흩어짐 36 × 순위 곡선)")
# 북아일랜드: 도구에 없고 다른 선수 자료(콜레인 2002-03 3위 1270, 크루세이더스 2011-12 5위 1250)가 있어 그 척도에 맞춤
man("Linfield FC", "2008-09", 1290, "북아일랜드 2008-09 2위 (추정, 다른 선수 자료 북아일랜드 3위 1270보다 조금 높게)")
