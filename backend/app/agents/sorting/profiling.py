"""① profiling: 업종 키워드 → 나올 수 있는 부산물 후보(코드). LLM은 안내 문장만."""
from __future__ import annotations

from app.agents._common import claim, ev, llm_note
from app.contracts import AgentResult
from app.tools.data import waste_name

ID = "profiling"
# 업종 키워드 → waste_codes.json 코드 (가입 때 고르기용 안내)
KEYWORDS = [
    (("사출", "플라스틱", "합성수지", "성형", "압출"), "51-03-01"),
    (("포장", "비닐", "필름"), "51-03-07"),
    (("전선", "케이블"), "51-03-99"),
    (("프레스", "금속", "철강", "기계", "용접", "절삭"), "51-29-01"),
    (("알루미늄", "비철", "주조", "다이캐스팅"), "51-29-02"),
    (("가구",), "51-20-27"),
    (("목재", "팔레트"), "51-20-99"),
    (("인쇄", "제지", "종이", "골판지", "박스"), "51-28-02"),
    (("식품", "음식", "외식"), "51-38-01"),
]


def run(ctx: dict, llm=None) -> AgentResult:
    industry = str((ctx.get("company") or {}).get("industry") or "").strip()
    cands, claims = [], []
    for words, code in KEYWORDS:
        hit = next((w for w in words if w in industry), None)
        if hit and not any(c["waste_code"] == code for c in cands):
            cands.append({"waste_code": code, "name": waste_name(code), "keyword": hit})
    if cands:
        listed = ", ".join(f"{c['name']}({c['waste_code']})" for c in cands)
        claims.append(claim(ID, f"입력한 업종에서 나올 수 있는 부산물 후보: {listed}. 가입 때 고르기용 안내이며 실제 배출 품목은 직접 확인해야 함",
                            "estimate", ev("input", "company.industry"), ev("assumption", "업종 키워드→부산물 후보 표(코드 내장)"),
                            ev("calc", "키워드 포함 여부")))
    else:
        claims.append(claim(ID, "업종 정보로는 부산물 후보를 좁히지 못함. 가입 때 직접 골라야 함", "question", ev("input", "company.industry")))
    note = llm_note(ID, llm, claims, "가입하는 공장 담당자에게 안내하는 말투로.", ctx)
    if note:
        claims.append(note)
    return AgentResult(agent_id=ID, claims=claims, data={"candidates": cands}, used_llm=bool(note))
