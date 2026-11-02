"""구미 가상 시나리오 시드. 실제 회사명은 쓰지 않는다. 실행: python -m seed.gumi_demo"""
from app.db.models import Base, Company
from app.db.session import SessionLocal, engine

CODE = "51-03-01"
# (이름, 역할, 사업자번호, 위도, 경도, 허가번호, 허가코드, 업종)
COMPANIES = [
    ("가상사출A", "factory", "000-00-00001", 36.1030, 128.3920, None, [], "플라스틱 사출"),
    ("가상사출B", "factory", "000-00-00002", 36.1065, 128.3975, None, [], "플라스틱 사출"),
    ("가상사출C", "factory", "000-00-00003", 36.1002, 128.3868, None, [], "플라스틱 사출"),
    ("가상리사이클", "recycler", "000-00-00004", 36.1250, 128.3600, "가상-허가-R01", [CODE], "폐합성수지 재활용"),
    ("가상운반", "hauler", "000-00-00005", 36.1180, 128.3700, "가상-허가-H01", [CODE], "폐기물 운반"),
    ("가상운영", "operator", "000-00-00006", 36.1190, 128.3440, None, [], "운영"),
]


def seed() -> dict:
    Base.metadata.create_all(engine)
    ids = {}
    with SessionLocal() as s:
        for name, role, biz, lat, lon, permit, codes, industry in COMPANIES:
            c = Company(name=name, role=role, biz_no=biz, lat=lat, lon=lon, permit_no=permit,
                        permit_codes=codes, industry=industry, verified=True)  # 데모라 허가 확인 끝난 상태
            s.add(c)
            s.flush()
            ids[name] = c.id
        s.commit()
    return ids


if __name__ == "__main__":
    for name, cid in seed().items():
        print(f"{name}: id={cid}  (X-Company-Id: {cid})")
