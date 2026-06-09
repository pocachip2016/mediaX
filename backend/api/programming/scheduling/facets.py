"""facets.py — 편성 연결 AI 추천용 통제어휘 (Content Understanding Profile)

LLM 출력을 자유서술 대신 이 vocab로 강제 → 매칭 일관·설명가능.
"""
from __future__ import annotations

VOCAB: dict[str, list[str]] = {
    "mood":     ["경쾌", "감성", "긴장", "따뜻", "어두움", "코믹", "로맨틱", "비장"],
    "occasion": ["주말", "가족시청", "심야", "명절", "연말", "비오는날", "몰아보기"],
    "audience": ["아동", "청소년", "성인", "가족", "시니어"],
    "tempo":    ["느림", "보통", "빠름"],
    "tone":     ["진지", "가벼움", "풍자", "다큐멘터리"],
    "themes":   ["성장", "복수", "우정", "가족", "생존", "범죄", "사랑", "전쟁", "음모"],
    # 감상 강도 — "강도가 높은 것만" 태깅(label형). 가족시청 적합도/충돌 판정 근거.
    "intensity": ["폭력", "잔인", "선정", "공포", "복잡"],
}

SETTING_ERA   = ["현대", "시대극", "근미래", "중세", "고대"]
SETTING_PLACE = ["한국", "미국", "일본", "유럽", "가상"]

FLAT_VOCAB: set[str] = {v for values in VOCAB.values() for v in values} | set(SETTING_ERA) | set(SETTING_PLACE)


def validate_facets(raw: dict) -> dict:
    """LLM 출력 facets에서 통제어휘 외 값 제거 후 반환.

    setting은 era/place 하위키 구조 처리.
    나머지 키는 리스트, 모르는 키 제거.
    """
    cleaned: dict = {}
    for key, allowed in VOCAB.items():
        vals = raw.get(key, [])
        if isinstance(vals, str):
            vals = [vals]
        cleaned[key] = [v for v in vals if v in allowed]

    setting_raw = raw.get("setting", {})
    if isinstance(setting_raw, dict):
        cleaned["setting"] = {
            "era":   [v for v in setting_raw.get("era", [])   if v in SETTING_ERA],
            "place": [v for v in setting_raw.get("place", []) if v in SETTING_PLACE],
        }
    return cleaned


def facet_overlap_score(facets_a: dict, facets_b: dict) -> float:
    """두 facets의 Jaccard 유사도 (0.0~1.0).

    simple flat set 비교: setting은 era/place 풀어서 포함.
    """
    def _flat(f: dict) -> set[str]:
        out: set[str] = set()
        for k, v in f.items():
            if k == "setting" and isinstance(v, dict):
                out.update(v.get("era", []))
                out.update(v.get("place", []))
            elif isinstance(v, list):
                out.update(v)
        return out

    a, b = _flat(facets_a), _flat(facets_b)
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)
