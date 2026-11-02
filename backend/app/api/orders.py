from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.api.deps import current_company, get_or_404, need_role
from app.api.schemas import AllbaroNo, Kg, Name, Note, Price, Text500, Won
from app.core.config import waste_names
from app.core.util import LEGAL_NOTE, MAX_FREIGHT, dec, iso, now, pct_diff, pct_text, won
from app.db.models import Bag, BagPass, Company, HandoverSection, Listing, Order, OrderHistory
from app.db.session import get_session
from app.services.flows import call_flow, dump
from app.services.orders import (change_status, goods_by_weight, held_goods, kg_sum, lock_order, pg_authorize, pg_set,
                                 settle)
from app.tools.calc import haversine_km

router = APIRouter(prefix="/v1")

TOLERANCE_PCT = 5   # 무게 허용 오차 ±5% (§8.4)


def has_permit(c: Company, code: str) -> bool:
    return code in (c.permit_codes or [])


class OrderIn(BaseModel):
    listing_id: int
    freight_cap_krw: Won


class AcceptIn(BaseModel):
    freight_krw: Won


class BagWeight(BaseModel):
    bag_id: int
    kg: Kg


class WeightsIn(BaseModel):
    bag_weights: list[BagWeight] = Field(max_length=50)


class InspectIn(WeightsIn):
    passed: bool
    note: Note | None = None


class ResolveIn(BaseModel):
    resolution: Literal["regrade", "treat", "return"]
    new_price_krw_per_kg: Price | None = None
    treatment_fee_krw: int | None = Field(default=None, ge=0, le=MAX_FREIGHT)
    note: Text500


def listing_bags(session: Session, order: Order) -> list[Bag]:
    return session.query(Bag).filter_by(listing_id=order.listing_id).order_by(Bag.id).all()


def check_weights(session: Session, order: Order, body: WeightsIn) -> list[dict]:
    """주문의 모든 마대 무게가 정확히 한 번씩 있어야 한다."""
    ids = sorted(w.bag_id for w in body.bag_weights)
    if ids != [b.id for b in listing_bags(session, order)]:
        raise HTTPException(400, "주문의 모든 마대 무게가 필요함")
    return [w.model_dump() for w in body.bag_weights]


def free_bags(session: Session, listing: Listing) -> None:
    """반송: 판매는 withdrawn, 마대는 판매에서 풀고 통과증 삭제(registered). 다시 등급을 받아야 재판매."""
    ids = [b.id for b in session.query(Bag).filter_by(listing_id=listing.id)]
    session.execute(update(Listing).where(Listing.id == listing.id).values(status="withdrawn"),
                    execution_options={"synchronize_session": False})
    if ids:
        session.execute(delete(BagPass).where(BagPass.bag_id.in_(ids)), execution_options={"synchronize_session": False})
        session.execute(update(Bag).where(Bag.id.in_(ids))
                        .values(listing_id=None, status="registered", grade=None, purity=None),
                        execution_options={"synchronize_session": False})


def order_party(session: Session, order_id: int, me: Company) -> tuple[Order, Listing]:
    order = get_or_404(session, Order, order_id)
    listing = session.get(Listing, order.listing_id)
    if me.role != "operator" and me.id not in (order.recycler_id, order.hauler_id, listing.factory_id):
        raise HTTPException(403, "이 주문의 당사자가 아님")
    return order, listing


def order_dict(session: Session, order: Order, listing: Listing) -> dict:
    hist = session.query(OrderHistory).filter_by(order_id=order.id).order_by(OrderHistory.id).all()
    return {"id": order.id, "status": order.status, "listing_id": order.listing_id, "goods_krw": order.goods_krw,
            "freight_cap_krw": order.freight_cap_krw, "held_krw": order.held_krw,
            "freight_krw": order.freight_krw, "factory_id": listing.factory_id, "recycler_id": order.recycler_id,
            "hauler_id": order.hauler_id, "waste_code": listing.waste_code, "total_kg": listing.total_kg,
            "bag_ids": [b.id for b in listing_bags(session, order)], "pickup_weights": order.pickup_weights,
            "inspect_weights": order.inspect_weights, "settlement": order.settlement,
            "allbaro_no": order.allbaro_no, "weight_warning": order.weight_warning,
            "dispute_reason": order.dispute_reason, "created_at": iso(order.created_at),
            "updated_at": iso(order.updated_at),
            "history": [{"from": h.from_status, "to": h.to_status, "by": h.by_company_id, "at": iso(h.at),
                         "note": h.note} for h in hist]}


@router.post("/orders", status_code=201)
def create_order(body: OrderIn, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "recycler", verified=True)
    listing = get_or_404(session, Listing, body.listing_id)
    if not has_permit(me, listing.waste_code):
        raise HTTPException(403, "이 폐기물 코드 허가가 없음")
    # 먼저 주문한 1곳만: 조건부 UPDATE
    got = session.execute(update(Listing).where(Listing.id == listing.id, Listing.status == "posted")
                          .values(status="sold"))
    if got.rowcount == 0:
        raise HTTPException(409, "게시 중인 판매가 아님")
    goods = won(dec(listing.total_kg) * dec(listing.price_krw_per_kg))
    order = Order(listing_id=listing.id, recycler_id=me.id, goods_krw=goods, freight_cap_krw=body.freight_cap_krw,
                  held_krw=held_goods(listing.total_kg, listing.price_krw_per_kg) + body.freight_cap_krw)
    session.add(order)
    session.flush()
    pg_authorize(session, order)
    change_status(session, order, "payment_held", None)
    factory = session.get(Company, listing.factory_id)
    ctx = {"order": {"id": order.id, "goods_krw": order.goods_krw, "freight_cap_krw": order.freight_cap_krw,
                     "held_krw": order.held_krw, "status": order.status},
           "listing": {"id": listing.id, "waste_code": listing.waste_code, "grade": listing.grade,
                       "total_kg": listing.total_kg, "price_krw_per_kg": listing.price_krw_per_kg},
           "factory": {"id": factory.id, "name": factory.name},
           "recycler": {"id": me.id, "name": me.name, "permit_no": me.permit_no, "permit_codes": me.permit_codes}}
    checklist = call_flow(session, "deal_check", ctx, [me.id, listing.factory_id])  # 호출 전 commit됨
    return {"id": order.id, "status": order.status, "goods_krw": order.goods_krw,
            "freight_cap_krw": order.freight_cap_krw, "held_krw": order.held_krw, "listing_id": listing.id,
            "checklist": dump(checklist)}


@router.get("/calls")
def list_calls(me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "hauler", verified=True)
    out = []
    for o in session.query(Order).filter_by(status="payment_held").order_by(Order.id):
        l = session.get(Listing, o.listing_id)
        if not has_permit(me, l.waste_code):
            continue
        f, r = session.get(Company, l.factory_id), session.get(Company, o.recycler_id)
        out.append({"order_id": o.id, "waste_code": l.waste_code, "waste_name": waste_names().get(l.waste_code, l.waste_code),
                    "total_kg": l.total_kg, "bag_count": len(listing_bags(session, o)),
                    "freight_cap_krw": o.freight_cap_krw, "distance_km": round(haversine_km(f.lat, f.lon, r.lat, r.lon), 1),
                    "pickup": {"lat": f.lat, "lon": f.lon}, "dropoff": {"lat": r.lat, "lon": r.lon}})
    return out


@router.post("/calls/{order_id}/accept")
def accept_call(order_id: int, body: AcceptIn, me: Company = Depends(current_company),
                session: Session = Depends(get_session)):
    need_role(me, "hauler", verified=True)
    order = get_or_404(session, Order, order_id)
    listing = session.get(Listing, order.listing_id)
    if not has_permit(me, listing.waste_code):
        raise HTTPException(403, "이 폐기물 코드 허가가 없음")
    if body.freight_krw > order.freight_cap_krw:
        raise HTTPException(400, f"운임이 구매자가 정한 상한({order.freight_cap_krw}원)을 넘음")
    # 먼저 수락한 1곳만: 조건부 UPDATE (두 번째는 rowcount 0 → 409)
    change_status(session, order, "dispatched", me.id, hauler_id=me.id, freight_krw=body.freight_krw)
    session.commit()
    return {"order_id": order_id, "status": "dispatched", "hauler_id": me.id}


def raise_if_former_hauler(session: Session, order: Order, me: Company) -> None:
    """재배차 뒤 이전 기사의 늦은 요청은 권한 없음(403)이 아니라 상태 충돌(409)로 답한다(§9.2)."""
    if me.role == "hauler" and session.query(OrderHistory).filter_by(order_id=order.id, by_company_id=me.id).first():
        raise HTTPException(409, "배차가 바뀐 주문")


def my_order_as(session: Session, order_id: int, me: Company, role: str) -> Order:
    """배정된 hauler / 주문한 recycler 확인."""
    need_role(me, role)
    order = get_or_404(session, Order, order_id)
    if me.id != (order.hauler_id if role == "hauler" else order.recycler_id):
        raise_if_former_hauler(session, order, me)
        raise HTTPException(403, "내 주문이 아님")
    return order


@router.post("/orders/{order_id}/pickup")
def pickup(order_id: int, body: WeightsIn, me: Company = Depends(current_company),
           session: Session = Depends(get_session)):
    order = my_order_as(session, order_id, me, "hauler")
    if order.status != "dispatched":
        raise HTTPException(409, f"{order.status} 상태에서는 수거 불가")
    weights = check_weights(session, order, body)
    listing = session.get(Listing, order.listing_id)
    diff = pct_diff(kg_sum(weights), listing.total_kg)
    warning = f"등록 무게와 {pct_text(diff)} 차이" if diff > TOLERANCE_PCT else None
    change_status(session, order, "picked_up", me.id, note=warning, pickup_weights=weights, picked_up_at=now(),
                  weight_warning=warning)
    session.commit()
    return {"status": order.status, **({"weight_warning": warning} if warning else {})}


@router.post("/orders/{order_id}/arrive")
def arrive(order_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    order = my_order_as(session, order_id, me, "hauler")
    change_status(session, order, "arrived", me.id)
    session.commit()
    return {"status": order.status}


@router.post("/orders/{order_id}/inspect")
def inspect(order_id: int, body: InspectIn, me: Company = Depends(current_company),
            session: Session = Depends(get_session)):
    order = my_order_as(session, order_id, me, "recycler")
    if order.status != "arrived":
        raise HTTPException(409, f"{order.status} 상태에서는 검사 불가")
    weights = check_weights(session, order, body)
    listing = session.get(Listing, order.listing_id)
    diff = pct_diff(kg_sum(weights), listing.total_kg)
    saved = {"inspect_weights": weights, "inspect_note": body.note}
    if not body.passed or diff > TOLERANCE_PCT:
        reason = "검사 불합격" if not body.passed else f"무게 차이 {pct_text(diff)}"
        change_status(session, order, "disputed", me.id, note=reason, dispute_reason=reason, **saved)  # 운영자 중재 대기
        session.commit()
        return {"status": order.status, "dispute_reason": reason}
    # 허용 오차 안: 검사 무게 × 단가로 비례 정산
    change_status(session, order, "confirmed", me.id, **saved)
    settlement = settle(order, goods_by_weight(weights, listing.price_krw_per_kg))
    change_status(session, order, "settled", None, settlement=settlement)
    pg_set(session, order, "captured")
    session.commit()
    return {"status": order.status, "settlement": order.settlement}


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    order = my_order_as(session, order_id, me, "recycler")
    change_status(session, order, "cancelled", me.id, settlement={"refund_krw": order.held_krw})
    pg_set(session, order, "refunded")
    session.execute(update(Listing).where(Listing.id == order.listing_id, Listing.status == "sold")
                    .values(status="posted"))  # 다시 게시
    session.commit()
    return {"status": order.status, "refund_krw": order.held_krw}


@router.post("/orders/{order_id}/release")
def release(order_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    """배차 후 수거 전 기사 포기(노쇼): 배정·운임을 지우고 콜 목록으로 돌려보낸다."""
    order = get_or_404(session, Order, order_id)
    if me.role != "operator" and me.id not in (order.hauler_id, order.recycler_id):
        raise_if_former_hauler(session, order, me)
        raise HTTPException(403, "배정 운반업체·주문한 재활용업체·운영자만 가능")
    # change_status가 읽은 배정 업체(hauler_id)를 조건에 넣으므로, 재배차 뒤 늦은 release는 409
    change_status(session, order, "payment_held", me.id, note="release", hauler_id=None, freight_krw=None)
    session.commit()
    return {"status": order.status}


@router.post("/admin/orders/{order_id}/resolve")
def resolve(order_id: int, body: ResolveIn, me: Company = Depends(current_company),
            session: Session = Depends(get_session)):
    need_role(me, "operator")
    order = get_or_404(session, Order, order_id)
    if order.status != "disputed":
        raise HTTPException(409, f"{order.status} 상태에서는 중재 불가")
    listing = session.get(Listing, order.listing_id)
    if body.resolution == "regrade":
        if body.new_price_krw_per_kg is None:
            raise HTTPException(400, "regrade에는 new_price_krw_per_kg가 필요")
        if dec(body.new_price_krw_per_kg) > dec(listing.price_krw_per_kg):
            raise HTTPException(400, "new_price_krw_per_kg는 원래 단가 이하만 가능")
        settlement, to = settle(order, goods_by_weight(order.inspect_weights, body.new_price_krw_per_kg)), "settled"
    elif body.resolution == "treat":
        if body.treatment_fee_krw is None:
            raise HTTPException(400, "treat에는 treatment_fee_krw가 필요")
        settlement, to = settle(order, 0, goods_refunded=True, factory_charge_krw=body.treatment_fee_krw,
                                recycler_fee_krw=body.treatment_fee_krw), "settled"
    else:
        settlement, to = settle(order, 0, goods_refunded=True), "returned"
    settlement = {**settlement, "resolution": body.resolution, "note": body.note}
    if body.resolution != "regrade":
        settlement["legal_note"] = LEGAL_NOTE
    change_status(session, order, to, me.id, note=f"{body.resolution}: {body.note}", settlement=settlement)
    pg_set(session, order, "captured")
    if body.resolution == "return":
        free_bags(session, listing)
    session.commit()
    return {"status": order.status, "settlement": order.settlement, **({"legal_note": LEGAL_NOTE} if "legal_note" in settlement else {})}


@router.get("/me/orders")
def my_orders(me: Company = Depends(current_company), session: Session = Depends(get_session)):
    q = session.query(Order, Listing).join(Listing, Listing.id == Order.listing_id)
    if me.role != "operator":
        q = q.filter((Order.recycler_id == me.id) | (Order.hauler_id == me.id) | (Listing.factory_id == me.id))
    out = []
    for o, l in q.order_by(Order.updated_at.desc(), Order.id.desc()):
        parties = {"factory": l.factory_id, "recycler": o.recycler_id, "hauler": o.hauler_id}
        role = next((r for r, cid in parties.items() if cid == me.id), me.role)
        names = [session.get(Company, cid).name for r, cid in parties.items() if cid is not None and cid != me.id]
        out.append({"id": o.id, "status": o.status, "role_in_order": role, "waste_name": waste_names().get(l.waste_code, l.waste_code),
                    "total_kg": l.total_kg, "goods_krw": o.goods_krw, "freight_cap_krw": o.freight_cap_krw,
                    "freight_krw": o.freight_krw, "counterparty_names": names, "updated_at": iso(o.updated_at)})
    return out


@router.get("/orders/{order_id}")
def get_order(order_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    order, listing = order_party(session, order_id, me)
    return order_dict(session, order, listing)


# ── 인계서 ──
class CarrierIn(BaseModel):
    vehicle_no: Name


class ProcessorIn(BaseModel):
    method: Text500


class NumberIn(BaseModel):
    allbaro_no: AllbaroNo


def sections(session: Session, order_id: int) -> dict:
    rows = session.query(HandoverSection).filter_by(order_id=order_id).all()
    return {r.section: r.data for r in rows}


def save_section(session: Session, order: Order, section: str, data: dict) -> dict:
    order = lock_order(session, order.id)   # 번호 입력과 칸 저장이 겹치지 않게 주문 행을 잠금(§9.2)
    if order.allbaro_no:
        raise HTTPException(409, "인계서 번호가 입력되어 잠김")
    row = session.query(HandoverSection).filter_by(order_id=order.id, section=section).first()
    if row is None:
        session.add(HandoverSection(order_id=order.id, section=section, data=data))
    else:
        row.data = data
    session.commit()
    return data


AFTER_PICKUP = ("picked_up", "arrived", "confirmed", "settled", "rated")
AFTER_CONFIRM = ("confirmed", "settled", "rated")


@router.get("/orders/{order_id}/handover")
def get_handover(order_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    order, _ = order_party(session, order_id, me)
    s = sections(session, order_id)
    return {"emitter": s.get("emitter"), "carrier": s.get("carrier"), "processor": s.get("processor"),
            "allbaro_no": order.allbaro_no}


def order_for_section(session: Session, order_id: int, me: Company, who: str):
    """칸 주인 확인(남의 칸은 403)."""
    order = get_or_404(session, Order, order_id)
    listing = session.get(Listing, order.listing_id)
    owner = {"factory": listing.factory_id, "hauler": order.hauler_id, "recycler": order.recycler_id}[who]
    if me.id != owner:
        raise HTTPException(403, "내 칸이 아님")
    return order, listing


@router.post("/orders/{order_id}/handover/emitter")
def handover_emitter(order_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    order, listing = order_for_section(session, order_id, me, "factory")
    if order.status not in AFTER_PICKUP:
        raise HTTPException(409, "수거 이후에 작성 가능")
    hauler = session.get(Company, order.hauler_id)
    data = {"company_name": me.name, "biz_no": me.biz_no, "waste_code": listing.waste_code,
            "waste_name": waste_names().get(listing.waste_code, listing.waste_code),
            "bags": order.pickup_weights, "carrier_name": hauler.name, "prepared_at": iso(now())}
    return save_section(session, order, "emitter", data)


@router.post("/orders/{order_id}/handover/carrier")
def handover_carrier(order_id: int, body: CarrierIn, me: Company = Depends(current_company),
                     session: Session = Depends(get_session)):
    order, _ = order_for_section(session, order_id, me, "hauler")
    if order.status not in AFTER_PICKUP:
        raise HTTPException(409, "수거 이후에 작성 가능")
    data = {"company_name": me.name, "vehicle_no": body.vehicle_no, "picked_up_at": iso(order.picked_up_at),
            "total_kg": float(kg_sum(order.pickup_weights)), "prepared_at": iso(now())}
    return save_section(session, order, "carrier", data)


@router.post("/orders/{order_id}/handover/processor")
def handover_processor(order_id: int, body: ProcessorIn, me: Company = Depends(current_company),
                       session: Session = Depends(get_session)):
    order, _ = order_for_section(session, order_id, me, "recycler")
    if order.status not in AFTER_CONFIRM:
        raise HTTPException(409, "확정 이후에 작성 가능")
    data = {"company_name": me.name, "received_kg": float(kg_sum(order.inspect_weights)),
            "method": body.method, "prepared_at": iso(now())}
    return save_section(session, order, "processor", data)


@router.post("/orders/{order_id}/handover/number")
def handover_number(order_id: int, body: NumberIn, me: Company = Depends(current_company),
                    session: Session = Depends(get_session)):
    order, _ = order_for_section(session, order_id, me, "factory")
    order = lock_order(session, order.id)
    if set(sections(session, order_id)) != {"emitter", "carrier", "processor"}:
        raise HTTPException(409, "인계서 3칸이 모두 채워진 뒤에만 가능")
    number = body.allbaro_no.strip()
    got = session.execute(update(Order).where(Order.id == order.id, Order.allbaro_no.is_(None))
                          .values(allbaro_no=number, updated_at=now()), execution_options={"synchronize_session": False})
    if got.rowcount == 0:
        raise HTTPException(409, "인계서 번호는 한 번만 입력할 수 있음")
    session.commit()
    return {"allbaro_no": number}
