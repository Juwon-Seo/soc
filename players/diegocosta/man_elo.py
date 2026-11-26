# 직접 정한 상대 Elo(build_diegocosta.py가 exec로 읽음). 모두 lv에 '추정' 또는 근거 표기.
import io as _io, contextlib as _cl
def _era():
    G_ = {"__file__": os.path.join(ROOT, "tools", "league_era_normalize.py"), "__name__": "x"}
    src = open(G_["__file__"], encoding="utf-8").read().replace("if '--apply' in sys.argv:", "if False:")
    argv = sys.argv; sys.argv = ["x"]
    with _cl.redirect_stdout(_io.StringIO()): exec(compile(src, "era", "exec"), G_)
    sys.argv = argv
    return G_["otarget"], G_["OSD"]
_OT, _OSD = _era()
# 이스라엘 1부 2012-13(14팀): 다른 UEFA 리그 시즌 수준(v1.222) 목표 평균 + 흩어짐 × 순위 곡선. 순위는 TM 표(우승 마카비 텔아비브 확인)
man("Hapoel Tel Aviv", "2012-13", half_up(_OT("Israel", 2013) + _OSD["Israel"] * cv(4, 14)), "이스라엘 2012-13 4위")
# 비유럽 리그(v1.217): 나라·시즌 목표 평균 + 흩어짐 × 순위 곡선
def w(o, y, cc, r, n, lab):
    man(o, y, half_up(WM["평균"][f"{cc}|{y}"] + WM["흩어짐"][cc] * cv(r, n)), lab)
w("Club Estudiantes de La Plata", "2024", "ARG", 12, 28, "아르헨티나 1부 2024 리가 12위/28팀")
w("Huachipato FC", "2024", "CHI", 12, 16, "칠레 1부 2024 12위/16팀")
w("Club The Strongest", "2024", "BOL", 2, 16, "볼리비아 1부 2024 종합 2위/16팀")
# 잉글랜드 리그 원 2015-16(24팀): 같은 시즌 기존 값(반슬리 6위 1522)과 같은 곡선(흩어짐 51.237)으로 7위
man("Scunthorpe United", "2015-16", half_up(1522 + 51.237 * (cv(7, 24) - cv(6, 24))), "리그 원 2015-16 7위")
# 스페인 3부(세군다 B): 다른 선수 자료 스페인 3부 1350과 같음
man("Real Jaén CF", "2012-13", 1350, "스페인 3부 (추정)")
# 가우슈 2024 상대: 그해 전국 리그 소속(영어 위키백과 2024 세리에 C·D 문서)으로 나눔. 세리에 C 1253, 4부 이하 1200에
#   2024 브라질 이동량 +59(같은 해 다른 선수 자료 4부 이하 1259와 같음)
man("SER Caxias do Sul (RS)", "2024", 1253 + 59, "브라질 세리에 C 2024 (추정, 세리에 C 참가 팀; 다른 선수 자료 세리에 C 1253과 같은 방식)")
man("Grêmio Esportivo Brasil (RS)", "2024", 1200 + 59, "브라질 4부 이하 2024 (추정, 세리에 D 참가 팀)")
man("Guarany de Bagé FC", "2024", 1200 + 59, "브라질 4부 이하 2024 (추정, 가우슈 팀, 세리에 A~D 참가 팀 아님)")
