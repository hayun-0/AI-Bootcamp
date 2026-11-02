"""엔진·세션. 테스트는 get_session을 override한다."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import database_url

_url = database_url()
if _url in ("sqlite://", "sqlite:///:memory:"):
    # 메모리 DB는 연결마다 새 DB가 되므로 연결 하나를 같이 쓴다
    engine = create_engine(_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
else:
    engine = create_engine(_url, connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session
