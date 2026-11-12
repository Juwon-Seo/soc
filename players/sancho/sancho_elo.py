"""산초: 순위표+기존 고정값과 직접 추정(상대 Elo, judgments.md 7절)"""
import unicodedata, re

def _norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

# 직접 추정(모두 lv에 '추정'): 순위가 있어도 기존 자료에 같은 리그의 해당 순위 값이 없어 이웃 순위 값의 중간값(곡선 맞춤 아님)
MAN = {
    (_norm("Legia Warszawa"), "2024-25"): (1490, "폴란드 2024-25 5위 (추정, 폴란드 2011-12 3위 1480과 2021-22 10위 1500의 중간값)"),
    (_norm("Djurgårdens IF"), "2024-25"): (1503, "스웨덴 알스벤스칸 2024 4위 (추정, 말뫼 2024 1위 1555와 2015 5위 1450의 중간값)"),
}
# 잉글랜드 챔피언십(24팀): 기존 자료의 순위별 고정값 중 7위(2015-16, 1642)
EN_FIX = {"ENG2": ("챔피언십", {7: 1642})}
def model(lg, season, r, n):
    if lg in EN_FIX and r in EN_FIX[lg][1]:
        assert n == 24
        return EN_FIX[lg][1][r], f"{EN_FIX[lg][0]} {season} {r}위"
    return None
