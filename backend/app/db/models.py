"""SQLAlchemy 모델. 시간은 UTC."""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


from app.core.util import now


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    biz_no: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    permit_no: Mapped[str | None] = mapped_column(String, nullable=True)
    permit_codes: Mapped[list] = mapped_column(JSON, default=list)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    verified: Mapped[bool] = mapped_column(default=False)


class Bag(Base):
    __tablename__ = "bags"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    waste_code: Mapped[str] = mapped_column(String)
    target_material: Mapped[str] = mapped_column(String)
    items: Mapped[list] = mapped_column(JSON)
    total_kg: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="registered")
    grade: Mapped[str | None] = mapped_column(String, nullable=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id"), nullable=True)
    purity: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    history: Mapped[list | None] = mapped_column(JSON, nullable=True)   # 등급 요청 기록(확인자 등)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BagPass(Base):
    """통과증."""
    __tablename__ = "passes"
    id: Mapped[int] = mapped_column(primary_key=True)
    bag_id: Mapped[int] = mapped_column(ForeignKey("bags.id"), unique=True)
    grade: Mapped[str] = mapped_column(String)


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    waste_code: Mapped[str] = mapped_column(String)
    grade: Mapped[str] = mapped_column(String)
    total_kg: Mapped[float] = mapped_column(Float)
    price_krw_per_kg: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    recycler_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    hauler_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="ordered")
    goods_krw: Mapped[int] = mapped_column(BigInteger)
    freight_cap_krw: Mapped[int] = mapped_column(BigInteger, default=0)   # 구매자가 정한 운임 상한
    held_krw: Mapped[int] = mapped_column(BigInteger, default=0)          # 보류 금액 = round(goods×1.05) + cap
    freight_krw: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pickup_weights: Mapped[list | None] = mapped_column(JSON, nullable=True)
    inspect_weights: Mapped[list | None] = mapped_column(JSON, nullable=True)
    inspect_note: Mapped[str | None] = mapped_column(String, nullable=True)
    settlement: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allbaro_no: Mapped[str | None] = mapped_column(String, nullable=True)
    weight_warning: Mapped[str | None] = mapped_column(String, nullable=True)
    dispute_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OrderHistory(Base):
    __tablename__ = "order_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    from_status: Mapped[str] = mapped_column(String)
    to_status: Mapped[str] = mapped_column(String)
    by_company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = 서버
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Payment(Base):
    """가짜 PG 결제."""
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    amount_krw: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String)  # authorized | captured | refunded


class HandoverSection(Base):
    __tablename__ = "handover_sections"
    __table_args__ = (UniqueConstraint("order_id", "section"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    section: Mapped[str] = mapped_column(String)  # emitter | carrier | processor
    data: Mapped[dict] = mapped_column(JSON)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("order_id", "rater_id", "target"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    rater_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    target: Mapped[str] = mapped_column(String)
    target_company_id: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)


class AgentRun(Base):
    """하네스 RunResult JSON 저장."""
    __tablename__ = "agent_runs"
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    flow: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON)
    company_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)   # 요청 회사 + 거래 당사자 (§9.4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
