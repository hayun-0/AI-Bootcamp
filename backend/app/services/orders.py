"""주문 상태 전이(계약 §4, v0.2 §8.5·8.6) + 가짜 PG.
모든 상태 변경은 `UPDATE ... WHERE id=? AND status=<이전 상태>`의 영향 행 수로 판정한다(0이면 409)."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.util import dec, dsum, now, won
from app.db.models import Order, OrderHistory, Payment

TRANSITIONS = {
    "ordered": {"payment_held"},
    "payment_held": {"dispatched", "cancelled"},
    "dispatched": {"picked_up", "payment_held"},   # payment_held = release(노쇼 대응)
    "picked_up": {"arrived"},
    "arrived": {"confirmed", "disputed"},
    "confirmed": {"settled"},
    "disputed": {"settled", "returned"},           # 운영자 중재
    "settled": {"rated"},
}


def lock_order(session: Session, order_id: int) -> Order:
    """주문 행을 SELECT … FOR UPDATE로 잠그고 최신값으로 다시 읽는다(PostgreSQL. SQLite는 무시)."""
    return session.query(Order).filter(Order.id == order_id).with_for_update().populate_existing().one()


def change_status(session: Session, order: Order, to: str, by: int | None, note: str | None = None, **values) -> None:
    """조건부 UPDATE로 전이. 표에 없는 전이·이미 바뀐 상태는 409. values는 같은 UPDATE에 함께 쓴다.
    읽은 시점의 배정 운반업체(hauler_id)도 조건에 넣어, 재배차 뒤 이전 기사의 늦은 요청을 막는다(§9.2)."""
    frm = order.status
    if to not in TRANSITIONS.get(frm, set()):
        raise HTTPException(409, f"{frm} → {to} 변경 불가")
    cond = [Order.id == order.id, Order.status == frm]
    if order.hauler_id is not None:
        cond.append(Order.hauler_id == order.hauler_id)
    got = session.execute(update(Order).where(*cond)
                          .values(status=to, updated_at=now(), **values), execution_options={"synchronize_session": False})
    if got.rowcount == 0:
        raise HTTPException(409, "이미 다른 요청이 상태를 바꿈")
    session.add(OrderHistory(order_id=order.id, from_status=frm, to_status=to, by_company_id=by, at=now(), note=note))
    session.flush()
    session.refresh(order)


# ── 가짜 PG ──
def pg_authorize(session: Session, order: Order) -> None:
    session.add(Payment(order_id=order.id, amount_krw=order.held_krw, status="authorized"))


def pg_set(session: Session, order: Order, status: str) -> None:
    pay = session.query(Payment).filter_by(order_id=order.id).one()
    pay.status = status


def kg_sum(weights: list[dict]):
    return dsum(w["kg"] for w in weights)


def held_goods(total_kg, price_krw_per_kg) -> int:
    """보류하는 물건값 = round(goods × 1.05). 검사 무게가 +5%까지 늘어도 공장 몫이 보류 안에 들어오도록
    반올림 전 정확한 곱(총kg × 단가 × 1.05)에서 한 번만 반올림한다."""
    return won(dec(total_kg) * dec(price_krw_per_kg) * Decimal("1.05"))


def settle(order: Order, factory_krw: int, goods_refunded: bool = False, **extra) -> dict:
    """정산 숫자. 공장 몫을 자르지 않는다(min 금지). 남는 돈(상한 − 운임 포함)은 구매자에게 환불.
    goods_refunded(처리·반송 중재): 물건값 전액 환불이므로 공장 몫은 환불 계산에서 뺀다.
    extra: treat의 factory_charge_krw·recycler_fee_krw 같은 추가 칸."""
    hauler = order.freight_krw or 0
    refund = order.held_krw - hauler if goods_refunded else order.held_krw - factory_krw - hauler
    if refund < 0:
        raise HTTPException(400, "정산액이 보류 금액을 넘음")
    return {"factory_krw": factory_krw, "hauler_krw": hauler, "platform_krw": 0, "refund_krw": refund, **extra}


def goods_by_weight(weights: list[dict], price_krw_per_kg: float) -> int:
    return won(kg_sum(weights) * dec(price_krw_per_kg))
