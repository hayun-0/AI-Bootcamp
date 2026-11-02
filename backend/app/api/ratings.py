from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_company, get_or_404
from app.api.schemas import Note
from app.db.models import Company, Listing, Order, Rating
from app.db.session import get_session
from app.services.orders import change_status, lock_order

router = APIRouter(prefix="/v1")


class RatingIn(BaseModel):
    order_id: int
    target: Literal["factory", "hauler", "recycler"]
    score: int = Field(ge=1, le=5)
    comment: Note | None = None


@router.post("/ratings", status_code=201)
def create_rating(body: RatingIn, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    order = get_or_404(session, Order, body.order_id)
    order = lock_order(session, order.id)   # 양쪽 첫 별점이 동시에 와도 rated로 가도록 순서를 세움(§9.2)
    listing = session.get(Listing, order.listing_id)
    if me.id not in (order.recycler_id, order.hauler_id, listing.factory_id):
        raise HTTPException(403, "이 주문의 당사자가 아님")
    target_id = {"factory": listing.factory_id, "hauler": order.hauler_id, "recycler": order.recycler_id}[body.target]
    if target_id == me.id:
        raise HTTPException(403, "자기 자신은 평가할 수 없음")
    if target_id is None or not order.allbaro_no:
        raise HTTPException(409, "인계서 번호가 입력된 뒤에만 평가 가능")
    if session.query(Rating).filter_by(order_id=order.id, rater_id=me.id, target=body.target).first():
        raise HTTPException(409, "이미 평가함")
    r = Rating(order_id=order.id, rater_id=me.id, target=body.target, target_company_id=target_id,
               score=body.score, comment=body.comment)
    session.add(r)
    session.flush()
    raters = {x.rater_id for x in session.query(Rating).filter_by(order_id=order.id)}
    if order.status == "settled" and {listing.factory_id, order.recycler_id} <= raters:
        try:
            change_status(session, order, "rated", None)
        except HTTPException:
            pass  # 다른 요청이 먼저 rated로 바꿈
    session.commit()
    return {"id": r.id}
