"""지휘 AI: 게이트를 통과한 주장만으로 요약을 만든다. 순서는 flow(규칙)가 정하고 LLM은 요약 문장만 쓴다.
LLM 요약은 게이트(주장에 없는 숫자 등)에 걸리면 1회 재요청, 또 걸리면 템플릿 요약."""
from __future__ import annotations

from app.contracts import Claim

from app.agents._common import mask_text
from app.harness.gates import check_summary, clean_llm_text, strip_risky
from app.tools.data import load_harness

TITLES = {"profile_company": "가입 안내", "grade_bag": "마대 등급", "listing_advice": "판매 추천", "deal_check": "거래 점검"}
SYSTEM = ("너는 폐기물 거래 앱의 지휘 AI다. 아래 항목(주장)만 근거로 쉬운 한국어 3문장 이내로 요약하라. "
          "문장 끝에 근거 항목의 [에이전트id:번호]를 붙여라. 항목에 없는 숫자, 법 조문, 업체명, 단정 표현은 쓰지 마라. 추정 항목은 추정이라고 쓰고, 등급 글자나 시세 범위 판단은 쓰지 마라(코드가 따로 쓴다). "
          'JSON {"summary": "..."} 로만 답하라.')
SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": False}


def template_summary(flow: str, claims: list[Claim]) -> str:
    if not claims:
        return f"{TITLES.get(flow, flow)}: 근거를 갖춘 항목이 없어 보여줄 내용이 없음. 사람이 직접 확인 필요"
    return f"{TITLES.get(flow, flow)}\n" + "\n".join(f"- {c.text}" for c in claims)


REL_TEXT = {"below": "시세 범위보다 낮습니다", "within": "시세 범위 안에 있습니다", "above": "시세 범위보다 높습니다"}


def fact_sentences(ctx: dict | None) -> str:
    """등급·가격-시세 관계 문장은 코드가 쓴다(등급 결과, 가격 관계 값에서 고정 문구로)."""
    res = (ctx or {}).get("results") or {}
    out = []
    grading = ((res.get("grading") or {}).get("data") or {}).get("grade")
    if grading is not None:
        g = grading.get("grade")
        out.append(f"등급은 {g}등급입니다." if g in ("A", "B", "C") else "등급을 매기지 못해 통과증이 없습니다.")
    rel = ((res.get("pricing") or {}).get("data") or {}).get("relation")
    if rel in REL_TEXT:
        out.append(f"올리려는 단가는 최근 지역별 {REL_TEXT[rel]}.")
    return " ".join(out)


def summarize(flow: str, claims: list[Claim], llm, log=None, ctx: dict | None = None) -> tuple[str, str]:
    """(요약, 'llm'|'template'). 예외를 내지 않는다. LLM 설명문 주장은 입력에서 뺀다.
    요약 = 코드가 쓴 등급·시세 관계 문장 + 남은 LLM 문장. LLM 문장 중 등급·시세 관계·단정 문장은 문장 단위로 뺀다."""
    base = [c for c in claims if not any(e.kind == "llm" for e in c.evidence)]
    if llm is None or not base:
        return template_summary(flow, base), "template"
    # LLM에는 사용자 문자열을 "[입력값]"으로 가린 주장 문장만 보낸다
    masked = [c.model_copy(update={"text": mask_text(c.text, ctx)}) for c in base]
    lines = [f"- [{c.agent_id}:{i}] {c.text}" for i, c in enumerate(masked, 1)]
    user = "\n".join(lines)
    retries = load_harness()["summary"].get("max_retries", 1)
    for attempt in range(retries + 1):
        try:
            reply = llm.chat(SYSTEM, user, SCHEMA)
            text = str((reply.data or {}).get("summary") or reply.text or "").strip()
        except Exception as e:
            if log:
                log.add("error", where="summary", message=str(e)[:200])
            break
        kept, dropped = strip_risky(clean_llm_text(text))
        reasons = check_summary(kept, masked) if kept else ["빈 요약" if not dropped else "남은 LLM 문장 없음: " + ", ".join(dropped)]
        if log:
            log.add("gate", target="summary", attempt=attempt + 1, passed=not reasons, reasons=reasons, dropped_sentences=len(dropped))
        if not reasons:
            facts = fact_sentences(ctx)
            return f"{facts} {kept}".strip(), "llm"
        user = "\n".join(lines) + "\n\n이전 요약이 다음 이유로 거절됨: " + "; ".join(reasons) + "\n항목에 있는 숫자만 쓰고, 등급이나 시세 비교는 쓰지 말고 다시 써라."
    return template_summary(flow, base), "template"
