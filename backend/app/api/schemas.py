"""입력 범위(ARCHITECTURE §8.1). 넘으면 400(RequestValidationError 핸들러)."""
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

from app.core.config import waste_names
from app.core.util import MAX_FREIGHT, round_kg, round_price


def _no_nul(s: str) -> str:
    if "\x00" in s:
        raise ValueError("NUL 문자 불가")
    return s


def _not_blank(s: str) -> str:
    if not s.strip():
        raise ValueError("공백만 불가")
    return s


def _known_waste_code(s: str) -> str:
    if s not in waste_names():
        raise ValueError("data/waste_codes.json에 없는 코드")
    return s


def _str(max_len: int):
    return Annotated[str, StringConstraints(min_length=1, max_length=max_len), AfterValidator(_no_nul), AfterValidator(_not_blank)]


Name = _str(100)                     # name, biz_no, vehicle_no, material 등
Text500 = _str(500)                  # method
Note = Annotated[str, StringConstraints(max_length=500), AfterValidator(_no_nul)]   # note, comment (빈 문자열 허용)
AllbaroNo = _str(50)
WasteCode = Annotated[str, AfterValidator(_known_waste_code)]
Lat = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Lon = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
def _positive(x: float) -> float:
    if x <= 0:
        raise ValueError("반올림 뒤 0 초과여야 함")
    return x


def _kg3(x: float) -> float:
    return _positive(round_kg(x))


def _price2(x: float) -> float:
    return _positive(round_price(x))


Kg = Annotated[float, Field(gt=0, le=2000, allow_inf_nan=False), AfterValidator(_kg3)]   # 소수 3자리
Price = Annotated[float, Field(gt=0, le=100_000, allow_inf_nan=False), AfterValidator(_price2)]   # 소수 2자리
Won = Annotated[int, Field(ge=1, le=MAX_FREIGHT)]
