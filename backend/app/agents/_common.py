"""에이전트 공통 도우미: 주장 만들기, LLM 설명문(게이트 전에 숫자 확인), 판매 입력 읽기."""
from __future__ import annotations

import re

from app.contracts import Claim, Evidence
from app.harness.gates import _numbers, clean_llm_text, strip_risky
from app.llm.base import LLMProvider
from app.tools.calc import canon_material, known_materials

NOTE_SYSTEM = (
    "너는 폐기물 거래 앱의 설명 도우미다. 아래 항목에 적힌 사실만 쉬운 한국어 두 문장 이내로 풀어 써라. "
    "새 숫자, 법 조문, 업체명, 단정 표현(확정, 불가, 불법)은 쓰지 마라. 항목에 없는 내용은 쓰지 마라."
)


def ev(kind: str, ref: str, label: str = "") -> Evidence:
    return Evidence(kind=kind, ref=ref, label=label)


def claim(agent_id: str, text: str, level: str, *evidence: Evidence) -> Claim:
    return Claim(agent_id=agent_id, text=text, level=level, evidence=list(evidence))


MASK = "[입력값]"


def user_strings(ctx: dict | None) -> list[str]:
    """사용자가 쓴 문자열(회사 이름·업종·메모·모르는 재질 이름). LLM 입력에서 가린다."""
    ctx = ctx or {}
    out: set[str] = set()
    for key in ("company", "factory", "recycler"):
        for f in ("name", "industry"):
            out.add(str((ctx.get(key) or {}).get(f) or ""))
    bags = [ctx.get("bag") or {}, *(ctx.get("bags") or [])]
    for b in bags:
        out.add(str(b.get("note") or ""))
        mats = [b.get("target_material"), *((i or {}).get("material") for i in (b.get("items") or []))]
        out.update(str(m) for m in mats if m)
    out.add(str((ctx.get("listing") or {}).get("target_material") or ""))
    known = known_materials()
    return sorted({s.strip() for s in out if len(s.strip()) >= 2 and canon_material(s) not in known}, key=len, reverse=True)


def mask_text(text: str, ctx: dict | None) -> str:
    for s in user_strings(ctx):       # 공백 개수가 달라도(정규화 전후) 같이 가림. 문장에는 원래 사용자 문자열이 없으므로 2차 방어선
        pat = r"\s*".join(re.escape(tok) for tok in s.split())
        text = re.sub(pat, MASK, text, flags=re.I)
    return text


def semantic_facts(ctx: dict | None, **override) -> dict:
    """뜻 검사 기준: 등급(등급 결과 > 판매 입력)과 단가-시세 관계(pricing 결과)."""
    ctx = ctx or {}
    res = ctx.get("results") or {}
    grading = ((res.get("grading") or {}).get("data") or {}).get("grade")
    grade = grading.get("grade") if grading else listing_basics(ctx)["grade"]
    facts = {"grade": grade if grade in ("A", "B", "C") else None,
             "relation": ((res.get("pricing") or {}).get("data") or {}).get("relation")}
    facts.update(override)
    return facts


def llm_note(agent_id: str, llm: LLMProvider | None, base: list[Claim], instruction: str = "",
             ctx: dict | None = None, **facts_override) -> Claim | None:
    """LLM이 base 주장들을 풀어 쓴 문장 1개. 실패하거나 새 숫자·뜻 모순이 있으면 None(예외 없음).
    LLM에는 사용자 문자열을 가린 주장 문장만 보낸다."""
    if llm is None or not base:
        return None
    masked = [mask_text(c.text, ctx) for c in base]
    user = "\n".join(f"- {t}" for t in masked)
    try:
        reply = llm.chat(NOTE_SYSTEM + (" " + instruction if instruction else ""), user)
    except Exception:
        return None
    text, _ = strip_risky(clean_llm_text((reply.text or "").strip()))    # 등급·시세 관계·단정 문장은 문장 단위로 뺌
    allowed = set().union(*(_numbers(t) for t in masked))
    if not text or _numbers(text) - allowed:
        return None
    seen, evidence = set(), [ev("llm", reply.model or llm.model, "LLM 설명문(사람 확인 필요)"),
                             ev("assumption", "LLM은 같은 에이전트의 위 주장만 풀어 씀")]
    for c in base:
        for e in c.evidence:
            if (e.kind, e.ref) not in seen:
                seen.add((e.kind, e.ref))
                evidence.append(e)
    return Claim(agent_id=agent_id, text=text, level="estimate", evidence=evidence)


def listing_basics(ctx: dict) -> dict:
    """listing_advice 입력에서 코드·등급·무게·품목·단가를 뽑는다. 없으면 None."""
    listing, bags = ctx.get("listing") or {}, ctx.get("bags") or []
    first = bags[0] if bags else {}
    total = listing.get("total_kg")
    if total is None and bags:
        total = sum(float(b.get("total_kg") or sum(float(i.get("kg", 0)) for i in b.get("items", []))) for b in bags)
    return {
        "waste_code": listing.get("waste_code") or first.get("waste_code"),
        "grade": listing.get("grade") or first.get("grade"),
        "total_kg": float(total) if total is not None else None,
        "target_material": listing.get("target_material") or first.get("target_material"),
        "price_krw_per_kg": listing.get("price_krw_per_kg"),
    }
