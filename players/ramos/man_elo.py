# 순위표(TM, 라모스 소속 리그) 밖 상대·통합표에 없는 상대 라벨(값은 라벨에서 계산). 순위 출처는 judgments.md '상대 Elo'.
man("FCSB", "2006-07", "루마니아 1부 2006-07 2위/18팀 (Liga I)")   # TM RO1 2006-07 표(tables/tm_RO1_2006.html): 1 디나모, 2 스테아우아
man("Atlético Astorga", "2023-24", "스페인 5부 2023-24 5위/18팀 (Tercera Federación Grupo VIII, 리그 수준 추정)")   # en.wiki 2023-24 Tercera Federación 8조 표 5위
# 몬테레이(리가MX): 경기 날짜에 진행 중이던 단계(클라우수라 2025 / 아페르투라 2025)의 정규리그 최종 순위(TM MEX1 2024-25·MEXA 2025-26 표, FotMob 표와 같음).
# 같은 팀·단계 값이 있으면 그 라벨 그대로(크루스 아술·푸마스·톨루카 = 론돈·에네르 발렌시아 자료).
_CL = "(Liga MX 클라우수라 2025, 경기 날짜에 진행 중이던 단계의 정규리그 순위)"
_AP = "(Liga MX 아페르투라 2025, 경기 날짜에 진행 중이던 단계의 정규리그 순위)"
FORCE.update({
 "4528311": f"리가MX 2024-25 18위/18팀 {_CL}",   # 산토스 라구나
 "4528280": f"리가MX 2024-25 3위/18팀 {_CL}",    # 크루스 아술
 "4528362": f"리가MX 2024-25 4위/18팀 {_CL}",    # 티그레스
 "4643422": f"리가MX 2025-26 13위/18팀 {_AP}",   # 네카사
 "4643486": f"리가MX 2025-26 10위/18팀 {_AP}",   # 푸마스
 "4778759": f"리가MX 2025-26 1위/18팀 {_AP}",    # 톨루카(리길야 준결승)
 "4571535": "MLS 2025 5위/30팀",                 # 밴쿠버(북중미 챔스 16강, 2025 MLS 전체 순위 = 메시·수아레스 등 기존 값)
})
# 승점 표 map 추가(오케스트레이터가 elo/league_points_other.json에 같은 줄을 넣음; 여기서는 메모리에서만 넣어 값이 같게 함)
MAP_ADD = [
 ("루마니아 1부 2006-07", "FCSB", [0, 1]),          # Steaua București (2위)
 ("리가MX 2024-25", "Tigres UANL@4", [2, 3]),       # Clausura 2025 표 4위 Tigres UANL
 ("리가MX 2025-26", "Club Necaxa@13", [1, 12]),     # Apertura 2025 표 13위 Necaxa
]
for _k, _n, _p in MAP_ADD:
    PTS.O["seasons"][_k].setdefault("map", {}).setdefault(_n, _p)
PTS._OS.clear() if hasattr(PTS, "_OS") else None
