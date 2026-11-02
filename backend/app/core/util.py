"""공통 도우미: 시간(UTC), 반올림, 입력 범위."""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

MAX_ID = 2_147_483_647   # int4 상한. 넘는 id는 '없음'으로 처리
MAX_FREIGHT = 10_000_000
MAX_GOODS = 10_000_000_000   # 판매 1건 물건값 상한 100억 원 (§9.1)
LEGAL_NOTE = "법률 자문 확인 필요"


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    """UTC ISO8601(+00:00). SQLite는 시간대를 잃으므로 UTC로 간주해 붙인다."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def dec(x) -> Decimal:
    return Decimal(str(x))


def won(x) -> int:
    """원 단위 사사오입(ROUND_HALF_UP)."""
    return int(dec(x).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def pct_diff(actual, expected) -> Decimal:
    """|actual-expected|/expected 를 퍼센트로(Decimal)."""
    return abs(dec(actual) - dec(expected)) / dec(expected) * 100


def pct_text(p: Decimal) -> str:
    return f"{p.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


def round_kg(x) -> float:
    """kg은 소수 3자리로 반올림해 저장."""
    return float(dec(x).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def round_price(x) -> float:
    """단가는 소수 2자리로 반올림해 저장."""
    return float(dec(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def dsum(values) -> Decimal:
    """실수 덧셈 금지: 모든 합은 Decimal(str(값))로."""
    return sum((dec(v) for v in values), Decimal(0))
