from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.deps import current_company, get_or_404, need_role
from app.api.schemas import Kg, Name, Note, WasteCode
from app.core.config import waste_names
from app.core.util import dsum, iso, now
from app.db.models import Bag, BagPass, Company
from app.db.session import get_session
from app.services.flows import call_flow, grade_from_result, local_grade

router = APIRouter(prefix="/v1")


class Item(BaseModel):
    material: Name
    kg: Kg


class BagIn(BaseModel):
    waste_code: WasteCode
    target_material: Name
    items: list[Item] = Field(min_length=1, max_length=20)
    note: Note | None = None

    @model_validator(mode="after")
    def total_limit(self):
        if dsum(i.kg for i in self.items) > 2000:
            raise ValueError("마대 합계는 2,000kg 이하")
        return self


class GradeIn(BaseModel):
    confirm_no_hazard: bool = False


def bag_dict(b: Bag) -> dict:
    """하네스에 넘기는 마대 정보(ctx['bag'])."""
    return {"id": b.id, "factory_id": b.factory_id, "waste_code": b.waste_code, "target_material": b.target_material,
            "items": b.items, "total_kg": b.total_kg, "note": b.note, "status": b.status}


def bag_view(session: Session, b: Bag) -> dict:
    p = session.query(BagPass).filter_by(bag_id=b.id).first()
    return {"id": b.id, "waste_code": b.waste_code, "waste_name": waste_names().get(b.waste_code, b.waste_code),
            "target_material": b.target_material, "total_kg": b.total_kg, "status": b.status, "grade": b.grade,
            "purity": b.purity, "pass_id": p.id if p else None, "qr": f"MDP-{p.id}-{b.id}" if p else None,
            "listing_id": b.listing_id, "created_at": iso(b.created_at)}


@router.post("/bags", status_code=201)
def create_bag(body: BagIn, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "factory")
    b = Bag(factory_id=me.id, waste_code=body.waste_code, target_material=body.target_material,
            items=[i.model_dump() for i in body.items], total_kg=float(dsum(i.kg for i in body.items)), note=body.note)
    session.add(b)
    session.commit()
    return bag_dict(b)


@router.get("/me/bags")
def my_bags(me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "factory")
    return [bag_view(session, b) for b in session.query(Bag).filter_by(factory_id=me.id).order_by(Bag.id.desc())]


@router.get("/bags/{bag_id}")
def get_bag(bag_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "factory")
    bag = get_or_404(session, Bag, bag_id)
    if bag.factory_id != me.id:
        raise HTTPException(403, "내 마대가 아님")
    return {**bag_view(session, bag), "items": bag.items, "reasons": bag.reasons or [], "note": bag.note}


@router.post("/bags/{bag_id}/grade")
def grade_bag(bag_id: int, body: GradeIn | None = None, me: Company = Depends(current_company),
              session: Session = Depends(get_session)):
    need_role(me, "factory")
    bag = get_or_404(session, Bag, bag_id)
    if bag.factory_id != me.id:
        raise HTTPException(403, "내 마대가 아님")
    if bag.listing_id is not None:
        raise HTTPException(409, "판매에 묶인 마대는 다시 등급을 매길 수 없음")
    confirm = bool(body and body.confirm_no_hazard)
    result = call_flow(session, "grade_bag", {"bag": {**bag_dict(bag), "confirm_no_hazard": confirm}}, [me.id])
    # 등급 숫자는 grading 에이전트의 코드 계산값만 쓴다. 하네스가 없을 때만 같은 규칙으로 직접 계산.
    grade = grade_from_result(result) or local_grade(bag, confirm)
    out = {"bag_id": bag.id, "grade": grade.model_dump(), "run_id": result.run_id if result else None}
    log = [*(bag.history or []), {"at": iso(now()), "by": me.id, "confirm_no_hazard": confirm, "grade": grade.grade}]
    # 호출하는 동안 판매에 묶였을 수 있으므로 조건부 UPDATE로 확정
    got = session.execute(update(Bag).where(Bag.id == bag.id, Bag.listing_id.is_(None))
                          .values(grade=grade.grade, purity=grade.purity, reasons=grade.reasons, history=log,
                                  status="rejected" if grade.grade is None else "graded"),
                          execution_options={"synchronize_session": False})
    if got.rowcount == 0:
        session.rollback()
        raise HTTPException(409, "판매에 묶인 마대는 다시 등급을 매길 수 없음")
    bag_pass = session.query(BagPass).filter_by(bag_id=bag.id).first()
    if grade.grade is None:
        if bag_pass:
            session.delete(bag_pass)
    else:
        if bag_pass is None:
            bag_pass = BagPass(bag_id=bag.id, grade=grade.grade)
            session.add(bag_pass)
        bag_pass.grade = grade.grade
        session.flush()
        out["pass_id"] = bag_pass.id
        out["qr"] = f"MDP-{bag_pass.id}-{bag.id}"
    session.commit()
    return out
