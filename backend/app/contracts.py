"""거래 서비스(분석팀 A)와 하네스(분석팀 B)가 함께 쓰는 타입. 바꾸려면 docs/ARCHITECTURE.md를 먼저 고친다."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    factory = "factory"      # 공장(파는 쪽)
    recycler = "recycler"    # 재활용업체(사는 쪽)
    hauler = "hauler"        # 운반업체
    operator = "operator"    # 운영자


class OrderStatus(str, Enum):
    ordered = "ordered"              # 주문
    payment_held = "payment_held"    # 결제 보류
    dispatched = "dispatched"        # 배차
    picked_up = "picked_up"          # 수거
    arrived = "arrived"              # 도착
    confirmed = "confirmed"          # 확정(검사 합격)
    settled = "settled"              # 정산
    rated = "rated"                  # 평가(양쪽 모두 별점)
    disputed = "disputed"            # 분쟁(검사 불합격 또는 무게 차이 ±5% 초과) → 운영자 중재
    cancelled = "cancelled"          # 취소(배차 전 구매자 취소)
    returned = "returned"            # 중재 결과 반송(반송 운반은 P1)


class ListingStatus(str, Enum):
    posted = "posted"            # 게시
    bundle_wait = "bundle_wait"  # 묶음 대기
    sold = "sold"                # 주문됨
    withdrawn = "withdrawn"      # 내림


EvidenceKind = Literal["law", "dataset", "calc", "assumption", "input", "llm"]
ClaimLevel = Literal["fact", "estimate", "assumption", "question"]


class Evidence(BaseModel):
    kind: EvidenceKind
    ref: str            # law → data/law_articles.json id, dataset → data/sources.json id, 그 밖은 식·필드명·모델명
    label: str = ""


class Claim(BaseModel):
    agent_id: str
    text: str
    level: ClaimLevel = "fact"
    evidence: list[Evidence] = Field(default_factory=list)
    blocked: bool = False
    block_reasons: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent_id: str
    ok: bool = True
    claims: list[Claim] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)   # 에이전트별 결과(계산값 등). 숫자는 코드가 만든 값만
    used_llm: bool = False
    error: str | None = None


class RunEvent(BaseModel):
    seq: int
    type: Literal["plan", "agent_start", "agent_done", "gate", "summary", "done", "error"]
    payload: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    run_id: str
    flow: str
    plan: list[str]                              # 실행한 에이전트 id 순서
    results: list[AgentResult]
    public_claims: list[Claim]                   # 게이트 통과한 주장만
    blocked_count: int
    summary: str
    summary_source: Literal["llm", "template"]
    llm: dict[str, Any]                          # {"provider": ..., "model": ..., "available": bool}
    events: list[RunEvent]


class GradeResult(BaseModel):
    """③ 등급·통과증 에이전트가 AgentResult.data["grade"]에 넣는 값."""
    target_material: str
    purity: float                    # 0~1, 목표 재질 무게 / 전체 무게
    grade: Literal["A", "B", "C"] | None   # None = 통과증 발급 안 함
    hazard: bool
    reasons: list[str] = Field(default_factory=list)
