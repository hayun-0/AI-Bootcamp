from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import exists, update
from sqlalchemy.orm import Session

from app.api.deps import current_company, get_or_404, need_role
from app.api.schemas import Price
from app.core.config import waste_names
from app.core.util import MAX_GOODS, MAX_ID, dec, dsum, won
from app.db.models import Bag, BagPass, Company, Listing, Order
from app.db.session import get_session
from app.services.flows import call_flow, dump

router = APIRouter(prefix="/v1")


class ListingIn(BaseModel):
    bag_ids: list[int] = Field(min_length=1, max_length=50)
    mode: Literal["now", "bundle"]
    price_krw_per_kg: Price

    @field_validator("bag_ids")
    @classmethod
    def unique(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("bag_ids 중복 불가")
        return v


def brief(l: Listing) -> dict:
    return {"id": l.id, "status": l.status, "waste_code": l.waste_code, "grade": l.grade, "total_kg": l.total_kg,
            "price_krw_per_kg": l.price_krw_per_kg}


def wname(code: str) -> str:
    return waste_names().get(code, code)


def listing_bags(session: Session, l: Listing) -> list[Bag]:
    return session.query(Bag).filter_by(listing_id=l.id).order_by(Bag.id).all()


@router.post("/listings", status_code=201)
def create_listing(body: ListingIn, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "factory")
    bags = [session.get(Bag, i) if 1 <= i <= MAX_ID else None for i in body.bag_ids]
    if any(b is None for b in bags):
        raise HTTPException(404, "없는 마대")
    if any(b.factory_id != me.id for b in bags):
        raise HTTPException(403, "내 마대가 아님")
    if any(session.query(BagPass).filter_by(bag_id=b.id).first() is None for b in bags):
        raise HTTPException(409, "통과증이 없는 마대")
    if len({(b.waste_code, b.grade) for b in bags}) != 1:
        raise HTTPException(400, "waste_code와 등급이 모두 같아야 함")
    if any(b.listing_id is not None for b in bags):
        raise HTTPException(409, "이미 다른 판매에 묶인 마대")
    total_kg = float(dsum(b.total_kg for b in bags))
    if won(dec(total_kg) * dec(body.price_krw_per_kg)) > MAX_GOODS:
        raise HTTPException(400, "판매 1건 물건값은 100억 원 이하")
    l = Listing(factory_id=me.id, mode=body.mode, status="bundle_wait" if body.mode == "bundle" else "posted",
                waste_code=bags[0].waste_code, grade=bags[0].grade, total_kg=total_kg,
                price_krw_per_kg=body.price_krw_per_kg)
    session.add(l)
    session.flush()
    # 마대 선점: 아직 안 묶인 마대만 한 번에 묶는다. 개수가 다르면 전부 롤백(동시 요청 방어)
    # 통과증이 있고 판매 등급과 같은 마대만(재등급과 경합하면 개수가 달라져 409)
    got = session.execute(update(Bag).where(Bag.id.in_([b.id for b in bags]), Bag.listing_id.is_(None),
                                            Bag.grade == l.grade,
                                            exists().where(BagPass.bag_id == Bag.id, BagPass.grade == l.grade))
                          .values(listing_id=l.id), execution_options={"synchronize_session": False})
    if got.rowcount != len(bags):
        session.rollback()
        raise HTTPException(409, "이미 다른 판매에 묶인 마대")
    others = session.query(Listing).filter(Listing.status.in_(("posted", "bundle_wait")), Listing.id != l.id).all()
    owners = {c.id: c for c in session.query(Company).filter(Company.id.in_({o.factory_id for o in others}))}
    ctx = {"listing": {**brief(l), "mode": l.mode, "factory_id": me.id},
           "bags": [{"id": b.id, "target_material": b.target_material, "total_kg": b.total_kg, "grade": b.grade} for b in bags],
           "nearby_listings": [{**brief(o), "factory_id": o.factory_id, "lat": owners[o.factory_id].lat,
                                "lon": owners[o.factory_id].lon} for o in others],
           "factory": {"id": me.id, "name": me.name, "lat": me.lat, "lon": me.lon}}
    advice = call_flow(session, "listing_advice", ctx, [me.id])  # 호출 전 commit됨
    return {**brief(l), "advice": dump(advice)}


@router.get("/listings")
def list_listings(waste_code: str | None = None, session: Session = Depends(get_session)):
    q = session.query(Listing).filter(Listing.status == "posted")
    if waste_code:
        q = q.filter(Listing.waste_code == waste_code)
    out = []
    for l in q.order_by(Listing.id):
        out.append({**brief(l), "factory_id": l.factory_id, "waste_name": wname(l.waste_code),
                    "bag_count": len(listing_bags(session, l)), "factory_name": session.get(Company, l.factory_id).name})
    return out


@router.get("/me/listings")
def my_listings(me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "factory")
    out = []
    for l in session.query(Listing).filter_by(factory_id=me.id).order_by(Listing.id.desc()):
        order = (session.query(Order).filter(Order.listing_id == l.id, Order.status != "cancelled")
                 .order_by(Order.id.desc()).first())
        out.append({**brief(l), "mode": l.mode, "waste_name": wname(l.waste_code),
                    "bag_ids": [b.id for b in listing_bags(session, l)], "order_id": order.id if order else None})
    return out


@router.get("/listings/{listing_id}")
def get_listing(listing_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    l = get_or_404(session, Listing, listing_id)
    if l.status not in ("posted", "bundle_wait") and me.role != "operator" and me.id != l.factory_id:
        # sold·withdrawn은 판매 공장·주문 당사자·operator만 (§9.4)
        party = session.query(Order).filter(Order.listing_id == l.id,
                                            (Order.recycler_id == me.id) | (Order.hauler_id == me.id)).first()
        if party is None:
            raise HTTPException(404, f"Listing {listing_id} 없음")
    bags = listing_bags(session, l)
    from app.tools.calc import known_materials, normalize_items
    known = known_materials()
    mats: dict[str, Decimal] = {}
    for b in bags:
        for it in b.items:
            k = next(iter(normalize_items([{"material": it["material"], "kg": 1}])), "")  # 별칭 → 표준 이름
            k = k if k in known else "[입력값]"  # 계약 9.3: 공개 화면에 사용자 재질명 원문 금지
            mats[k] = mats.get(k, Decimal(0)) + dec(it["kg"])
    total = sum(mats.values(), Decimal(0))
    purities = [(dec(b.purity), dec(b.total_kg)) for b in bags if b.purity is not None]
    weight = sum((kg for _, kg in purities), Decimal(0))
    f = session.get(Company, l.factory_id)
    return {**brief(l), "waste_name": wname(l.waste_code),
            "target_material": bags[0].target_material if bags else None,
            "purity_avg": round(float(sum((p * kg for p, kg in purities), Decimal(0)) / weight), 4) if weight else None,
            "composition": {k: round(float(v / total), 4) for k, v in mats.items()} if total else {},
            "bag_count": len(bags), "factory_name": f.name,
            "area": {"lat": round(f.lat, 2), "lon": round(f.lon, 2)}}


@router.post("/listings/{listing_id}/withdraw")
def withdraw_listing(listing_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "factory")
    l = get_or_404(session, Listing, listing_id)
    if l.factory_id != me.id:
        raise HTTPException(403, "내 판매가 아님")
    got = session.execute(update(Listing).where(Listing.id == l.id, Listing.status.in_(("posted", "bundle_wait")))
                          .values(status="withdrawn"), execution_options={"synchronize_session": False})
    if got.rowcount == 0:
        raise HTTPException(409, "게시·묶음 대기 중인 판매만 내릴 수 있음")
    session.execute(update(Bag).where(Bag.listing_id == l.id).values(listing_id=None),
                    execution_options={"synchronize_session": False})  # 마대 풀림
    session.commit()
    return {"id": l.id, "status": "withdrawn"}
