"""② vision(P0는 사진 대신 품목 입력): items 정규화·구성비 계산. note는 LLM이 재질 후보만 추출(등급에 안 씀)."""
from __future__ import annotations

import re

from app.agents._common import MASK, claim, ev
from app.contracts import AgentResult
from app.tools.calc import alias_map, canon_material, fmt, hazard_terms, known_materials, normalize_items
from app.tools.data import assumptions

ID = "vision"
SCHEMA = {"type": "object", "properties": {"candidates": {"type": "array", "items": {"type": "string"}}},
          "required": ["candidates"], "additionalProperties": False}
SYSTEM = ("마대에 붙은 메모에서 언급된 재질 이름만 골라 영어 소문자 짧은 단어 목록으로 돌려줘. "
          "메모에 없는 재질은 넣지 마라. 무게나 비율은 쓰지 마라.")


def run(ctx: dict, llm=None) -> AgentResult:
    bag = ctx.get("bag") or {}
    mats = normalize_items(bag.get("items"))
    total = sum(mats.values())
    claims, data = [], {"materials": mats, "total_kg": round(total, 3), "composition": {}, "note_candidates": []}
    if total > 0:
        comp = {m: round(kg / total, 4) for m, kg in mats.items()}
        data["composition"] = comp
        known = known_materials()
        shown: dict[str, float] = {}
        for m, r in comp.items():                  # 모르는 재질 이름(사용자 문자열)은 문장에 "[입력값]"으로 묶어 표시
            key = m if m in known else MASK
            shown[key] = shown.get(key, 0.0) + r
        parts = ", ".join(f"{m} {fmt(round(r * 100, 1))}%" for m, r in sorted(shown.items(), key=lambda x: -x[1]))
        claims.append(claim(ID, f"입력한 품목 기준 총 {fmt(round(total, 3))} kg, 구성비: {parts}", "fact",
                            ev("input", "bag.items"), ev("calc", "재질 kg / 전체 kg")))
    else:
        claims.append(claim(ID, "입력한 품목에 무게가 없어 구성비를 계산하지 못함", "question", ev("input", "bag.items")))

    used = False
    note = str(bag.get("note") or "").strip()
    hz_terms = {h.lower() for h in assumptions()["hazard_materials"]}
    note_hz = hazard_terms(note, hz_terms)
    data["note_hazard"] = note_hz
    if note_hz:
        claims.append(claim(ID, f"메모에 위험 재질 언급: {', '.join(note_hz)}(사람 확인 필요)", "estimate",
                            ev("input", "bag.note", "메모에 적힌 말을 그대로 찾음"), ev("assumption", "hazard_materials(팀 가정) 단어 일치")))
    if note and llm is not None:
        try:
            reply = llm.chat(SYSTEM, note, SCHEMA)
            used = True
            cands = _note_candidates(note, (reply.data or {}).get("candidates") or [])
            data["note_candidates"] = cands
            if cands:
                text = "메모에서 읽은 재질 후보(사람 확인 필요, 등급 계산에는 쓰지 않음): " + ", ".join(cands)
                claims.append(claim(ID, text, "estimate", ev("llm", reply.model or llm.model, "자유 서술에서 추출(사람 확인 필요)"),
                                    ev("assumption", "note 추출값은 후보일 뿐 등급 계산에 쓰지 않음")))
        except Exception:
            pass
    return AgentResult(agent_id=ID, claims=claims, data=data, used_llm=used)


def _note_candidates(note: str, raw: list) -> list[str]:
    """LLM 후보 중 메모에 실제로 나오는 말(별칭 포함)이면서 아는 재질인 것만, 표준 이름으로, 최대 5개."""
    low, known, aliases = " ".join(note.lower().split()), known_materials(), alias_map()
    out: list[str] = []
    for c in raw:
        c = str(c).strip().lower()[:30]
        if not c or any(ch.isdigit() for ch in c):
            continue
        canon = canon_material(c)
        names = {c, canon} | {a for a, m in aliases.items() if m == canon}
        if canon in known and any(re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", low) for n in names) and canon not in out:
            out.append(canon)
    return out[:5]
