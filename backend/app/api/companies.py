import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_company, get_or_404, need_role
from app.api.schemas import Lat, Lon, Name, WasteCode
from app.contracts import Role
from app.db.models import Company
from app.db.session import get_session
from app.services.flows import call_flow, dump

router = APIRouter(prefix="/v1")


class CompanyIn(BaseModel):
    name: Name
    role: Role
    biz_no: Name
    lat: Lat
    lon: Lon
    permit_no: Name | None = None
    permit_codes: list[WasteCode] = Field(default=[], max_length=30)
    industry: Name | None = None


def company_dict(c: Company) -> dict:
    return {"id": c.id, "name": c.name, "role": c.role, "verified": c.verified, "permit_codes": c.permit_codes,
            "lat": c.lat, "lon": c.lon}


@router.post("/companies", status_code=201)
def create_company(body: CompanyIn, x_operator_token: str | None = Header(default=None),
                   session: Session = Depends(get_session)):
    if body.role == Role.operator:
        # 운영자는 공개 가입 불가: 환경변수 토큰이 설정돼 있고 헤더가 같을 때만
        token = os.environ.get("OPERATOR_BOOTSTRAP_TOKEN", "")
        if not token or not x_operator_token or not secrets.compare_digest(token, x_operator_token):
            raise HTTPException(403, "운영자는 가입으로 만들 수 없음")
    c = Company(name=body.name, role=body.role.value, biz_no=body.biz_no, lat=body.lat, lon=body.lon,
                permit_no=body.permit_no, permit_codes=body.permit_codes, industry=body.industry,
                verified=body.role in (Role.factory, Role.operator))  # recycler·hauler는 운영자 확인 필요
    session.add(c)
    session.flush()
    out = {"id": c.id, "name": c.name, "role": c.role, "verified": c.verified, "permit_codes": c.permit_codes}
    if c.role == "factory":
        ctx = {"company": {"id": c.id, "name": c.name, "industry": c.industry, "biz_no": c.biz_no}}
        out["guide"] = dump(call_flow(session, "profile_company", ctx, [c.id]))
    session.commit()
    return out


@router.post("/admin/companies/{company_id}/verify")
def verify_company(company_id: int, me: Company = Depends(current_company), session: Session = Depends(get_session)):
    need_role(me, "operator")
    target = get_or_404(session, Company, company_id)
    if target.role in ("recycler", "hauler") and not target.permit_codes:
        raise HTTPException(409, "허가 코드(permit_codes)가 없는 업체는 확인할 수 없음")
    target.verified = True
    session.commit()
    return {"id": target.id, "verified": True}


@router.get("/me")
def me_info(me: Company = Depends(current_company)):
    return company_dict(me)
