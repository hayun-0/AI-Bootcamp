"""③ grading: 순도 = target 재질 kg / 전체 kg. 위험 재질이 있으면 등급 없음. LLM 안 씀."""
from __future__ import annotations

from app.agents._common import MASK, claim, ev
from app.contracts import AgentResult, GradeResult
from app.tools.calc import compute_grade, known_materials
from app.tools.data import assumptions

ID = "grading"


def run(ctx: dict, llm=None) -> AgentResult:
    bag = ctx.get("bag") or {}
    g = compute_grade(str(bag.get("target_material") or ""), bag.get("items"), bag.get("note"),
                      bool(bag.get("confirm_no_hazard", False)))
    th = assumptions()["grade_thresholds"]
    grade = GradeResult(target_material=g["target_material"], purity=g["purity"], grade=g["grade"],
                        hazard=g["hazard"], reasons=g["reasons"])
    base = [ev("input", "bag.items"), ev("calc", "순도 = 목표 재질 kg / 전체 kg"),
            ev("assumption", "grade_thresholds(구매자 요구 스펙 확인 전 팀 가정)")]
    cr = g["claim_reasons"]                       # 문장에는 사용자 문자열 대신 "[입력값]"(원문은 data.grade.reasons)
    tm = grade.target_material if grade.target_material in known_materials() else MASK
    crit = f"기준: A {th['A']}, B {th['B']}, C {th['C']} 이상"
    if grade.grade:
        text = f"{tm} 순도 {grade.purity}로 {grade.grade}등급 ({crit})"
        if cr:
            text += "; " + "; ".join(cr)
    elif grade.hazard:
        text = f"위험 재질이 들어 있어 등급을 매기지 않음, 통과증 없음 ({'; '.join(cr)})"
    elif g["note_hazard"] and any(r.startswith("메모에") for r in grade.reasons):
        text = f"{tm} 순도 {grade.purity}, 통과증 보류 ({'; '.join(cr)})"
    else:
        text = f"{tm} 순도 {grade.purity}, 통과증 없음 ({'; '.join(cr)})"  # 계약 8.9: 등급 없으면 등급 글자 금지
    claims = [claim(ID, text, "fact", *base)]
    return AgentResult(agent_id=ID, claims=claims, data={"grade": grade.model_dump(), "note_hazard": g["note_hazard"], "total_kg": g["total_kg"]})
