"""공통: 헤더 인증, 역할 확인, 에러 도우미."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.util import MAX_ID
from app.db.models import Company
from app.db.session import get_session


def current_company(x_company_id: str | None = Header(default=None), session: Session = Depends(get_session)) -> Company:
    try:
        cid = int(x_company_id) if x_company_id else 0
    except ValueError:
        cid = 0
    company = session.get(Company, cid) if 1 <= cid <= MAX_ID else None   # 범위 밖 id는 '없는 회사'(401)
    if company is None:
        raise HTTPException(401, "X-Company-Id 헤더가 없거나 없는 회사")
    return company


def need_role(company: Company, *roles: str, verified: bool = False) -> None:
    if company.role not in roles:
        raise HTTPException(403, "이 역할은 사용할 수 없음")
    if verified and not company.verified:
        raise HTTPException(403, "운영자 허가 확인 전")


def get_or_404(session: Session, model, obj_id: int):
    obj = session.get(model, obj_id) if isinstance(obj_id, int) and 1 <= obj_id <= MAX_ID else None
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {obj_id} 없음")
    return obj
