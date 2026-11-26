# 헐크 상대 라벨(순위 출처는 judgments.md 5절). build_hulk.py가 exec로 읽음.

# ── 페널티(감점) 시즌: elo/penalty_seasons.json — 감점 전 순위
PEN = {}
for c_ in json.load(open(os.path.join(ELO, "penalty_seasons.json"), encoding="utf-8"))["changes"]:
    PEN[(c_["line"].split(" [")[0], key(c_["team"]))] = (c_["official"], c_["onfield"])

def br_label(o, y, state=None):
    """브라질 클럽의 그해 전국 리그 단계 순위(세리에 A·B는 TM 순위표, C·D는 포르투갈어 위키백과 최종 순위)."""
    for lg, nm in (("BRA1", "브라질 세리에 A"), ("BRA2", "브라질 세리에 B")):
        t = RANKS.get((lg, y), {})
        for n_ in nm_cands(o):
            if key(n_) in t:
                r, n, _ = t[key(n_)]
                pe = PEN.get((f"{nm} {y}", key(n_)))
                if pe and pe[0] == r: return f"{nm} {y} {pe[1]}위/{n}팀 (감점 전 순위)"
                return f"{nm} {y} {r}위/{n}팀"
    return None

# TM 경기 이름 → TM 순위표 이름(같은 클럽의 그 시즌 이름)
NAME_ALIAS.update({
 "Thespa Gunma": "Thespa Kusatsu", "Hokkaido Consadole Sapporo": "Consadole Sapporo", "Associação Naval 1893": "Naval 1º de Maio",
 "Spartak Vladikavkaz": "Alania Vladikavkaz", "Akhmat Grozny": "Terek Grozny",
 "Shandong Taishan": "Shandong Luneng Taishan", "Tianjin Tianhai": ["Tianjin Quanjian", "Tianjin Tianhai (-2019)"],
 "Guizhou FC": ["Guizhou Hengfeng Zhicheng", "Guizhou Hengfeng"], "Shanghai Shenhua": "Shanghai Greenland Shenhua",
 "Guangzhou City": "Guangzhou R&F", "Dalian Professional": "Dalian Yifang", "Wuhan Yangtze": "Wuhan Zall",
 "Guangzhou FC": "Guangzhou Evergrande Taobao", "Jiangsu FC": "Jiangsu Suning", "Hebei FC": "Hebei China Fortune",
 "Henan FC": "Henan Jianye", "Chongqing Liangjiang Athletic": ["Chongqing Dangdai Lifan", "Chongqing Lifan"], "Liaoning FC": "Liaoning FC",
 "Changchun Yatai": "Changchun Yatai", "Tianjin Jinmen Tiger": "Tianjin Teda", "Beijing Guoan": "Beijing Guoan",
 "Shenzhen FC": "Shenzhen FC", "Zhejiang FC": "Hangzhou Greentown", "Cangzhou Mighty Lions": "Shijiazhuang Ever Bright",
 "Qingdao FC": "Qingdao Huanghai", "Ulsan HD FC": "Ulsan Hyundai",
})
man("Sydney FC", "2019-04-23", "호주 A리그 2018-19 2위/10팀")   # 2019 AFC 조별 4월: A리그 2018-19 정규리그 2위(통합표 값)
