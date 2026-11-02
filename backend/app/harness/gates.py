"""게이트 3개: evidence(근거), wording(표현), privacy(개인정보). 막힌 주장은 blocked=true.
요약 검사(check_summary)는 주장에 없는 숫자와 위 규칙을 본다."""
from __future__ import annotations

import re
import unicodedata

from app.contracts import Claim
from app.tools.data import forbidden_phrases, law_ids, source_ids

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
LAW_WORD_RE = re.compile(r"(제\s*\d+\s*조|시행령|시행규칙|별표|\bR-\d|폐기물관리법|순환경제법)")
NUMBER_OK_KINDS = {"dataset", "calc", "input", "assumption", "law"}
PHONE_RE = re.compile(r"(?<!\d)0\d{1,2}[-.\s]\d{3,4}[-.\s]\d{4}(?!\d)|(?<!\d)0\d{9,10}(?!\d)"
                      r"|\+\d{1,3}[-.\s]?\(?\d{1,4}\)?(?:[-.\s]?\d{2,4}){2,3}(?!\d)"      # 국제 형식 +82-10-…
                      r"|(?<!\d)1[5-9]\d{2}[-.\s]\d{4}(?!\d)")                               # 대표번호 1588-xxxx
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
RRN_RE = re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)")
UNKNOWN_AS_NONE_RE = re.compile(r"(모르|미확인|확인되지 않|알 수 없).{0,12}(없다|없음|아니다)")


# 한글 수 표현("삼십 퍼센트", "두 배", "백 킬로")도 숫자로 센다
_SINO = "[일이삼사오육칠팔구]"
_KO_NUM = (rf"(?<![가-힣])(?:(?:{_SINO}?[십백천만억])+{_SINO}?|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스물|서른|마흔|쉰|하나|둘|셋|넷)"
           r"\s?(?:퍼센트|프로|배|킬로그램|킬로미터|킬로|그램|미터|톤|원|개|건|곳|군데|명|%)(?![가-힣])")
KO_NUM_RE = re.compile(_KO_NUM.replace("(?![가-힣])", "(?:(?![가-힣])|(?=[을를이가은는의에로과와도만입씩쯤짜라며]))"))
SENT_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+|\n+")
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
GRADE_WORD_RE = re.compile(r"(?<![A-Za-z])[A-Ca-c]\s*(?:등급|급)|등급[\s:은는이가의]{0,4}[A-Ca-c](?![A-Za-z])")
PRICE_KW_RE = re.compile(r"범위|시세|적정|비싸|비싼|비쌉|비쌌|저렴|(?<![가-힣])싼(?![가-힣])|(?<![가-힣])싸(?:다|요|게|니)|낮|높|초과|미만|이상|이하")
PRICE_CTX_RE = re.compile(r"단가|가격|시세|범위|원\s*/\s*k?g|값|판매가|매입가|적정|비싸|비싼|비쌉|저렴")
OVERCONFIDENT_RE = re.compile(r"절감\s*효과가\s*있|절약\s*할\s*수\s*있|아낄\s*수\s*있|아껴\s*질|확실|보장|반드시")


def _norm(text: str) -> str:
    return ZERO_WIDTH_RE.sub("", unicodedata.normalize("NFKC", text))


def risky_sentence(sentence: str) -> str | None:
    """LLM 문장이 코드만 말해야 하는 내용(등급, 가격-시세 관계)이나 단정 표현이면 이유, 아니면 None."""
    s = _norm(sentence)
    if GRADE_WORD_RE.search(s):
        return "등급 판단 문장"
    if PRICE_KW_RE.search(s) and PRICE_CTX_RE.search(s):
        return "가격-시세 관계 문장"
    if OVERCONFIDENT_RE.search(s):
        return "단정 표현"
    return None


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"(?<=[.!?])(?=[가-힣])", " ", text)
    return [p.strip() for p in SENT_SPLIT_RE.split(text) if p.strip()]


def strip_risky(text: str) -> tuple[str, list[str]]:
    """문장 단위로 위험 문장만 뺀 글과 뺀 이유 목록."""
    keep, dropped = [], []
    for sent in split_sentences(text):
        why = risky_sentence(sent)
        (dropped.append(why) if why else keep.append(sent))
    return " ".join(keep), dropped


def _numbers(text: str) -> set[str]:
    nums = {n.replace(",", "").rstrip(".") for n in NUM_RE.findall(text)}
    return nums | {m.group(0).replace(" ", "") for m in KO_NUM_RE.finditer(text)}


def semantic_reasons(text: str, facts: dict | None = None) -> list[str]:
    """LLM 글에 등급·가격 관계·단정 문장이 남아 있으면 이유(그런 문장은 코드가 쓴다). facts는 호환용으로만 받음."""
    return [f"semantic: {why}" for why in {risky_sentence(x) for x in split_sentences(text)} if why]


def evidence_reasons(c: Claim) -> list[str]:
    r: list[str] = []
    if not c.evidence:
        return ["evidence: 근거 없음"]
    laws, srcs = law_ids(), source_ids()
    for e in c.evidence:
        if e.kind == "law" and e.ref not in laws:
            r.append(f"evidence: 없는 법 조문 id {e.ref}")
        if e.kind == "dataset" and e.ref not in srcs:
            r.append(f"evidence: 없는 데이터셋 id {e.ref}")
    kinds = {e.kind for e in c.evidence}
    if _numbers(c.text) and not (kinds & NUMBER_OK_KINDS):
        r.append("evidence: 숫자가 있는데 dataset/calc/input/assumption/law 근거 없음")
    if LAW_WORD_RE.search(c.text) and "law" not in kinds:
        r.append("evidence: 법을 말하는데 law 근거 없음")
    if c.level in ("estimate", "assumption") and not (kinds & {"assumption", "calc"}):
        r.append("evidence: estimate/assumption 주장에 assumption/calc 근거 없음")
    return r


def text_reasons(text: str) -> list[str]:
    r: list[str] = []
    for ph in forbidden_phrases():
        if ph in text:
            r.append(f"wording: 금지 표현 '{ph}'")
    if UNKNOWN_AS_NONE_RE.search(text):
        r.append("wording: '모름'을 '없음'으로 바꿔 말함")
    if PHONE_RE.search(text):
        r.append("privacy: 전화번호 모양")
    if EMAIL_RE.search(text):
        r.append("privacy: 이메일 모양")
    if RRN_RE.search(text):
        r.append("privacy: 주민번호 모양")
    return r


def apply_gates(claims: list[Claim], facts: dict | None = None) -> tuple[list[Claim], int]:
    """각 주장에 게이트 적용. (통과한 주장 목록, 막힌 수). 원본 claim.blocked/block_reasons도 채운다.
    facts가 있으면 LLM이 쓴 주장(근거에 llm)에 뜻 검사도 한다."""
    public, blocked = [], 0
    for c in claims:
        reasons = evidence_reasons(c) + text_reasons(c.text)
        if any(e.kind == "llm" for e in c.evidence):
            reasons += semantic_reasons(c.text)
        if reasons:
            c.blocked, c.block_reasons = True, reasons
            blocked += 1
        else:
            public.append(c)
    return public, blocked


def check_summary(text: str, public_claims: list[Claim], facts: dict | None = None) -> list[str]:
    """요약 글 검사: 주장에 없는 숫자(한글 수 표현 포함), 금지 표현, 개인정보, 등급·시세 뜻."""
    allowed: set[str] = set()
    for c in public_claims:
        allowed |= _numbers(c.text)
    body = re.sub(r"\[[a-z_]+:\d+\]", "", text)     # [agent:n] 인용 표시는 숫자로 세지 않음
    r = [f"provenance: 주장에 없는 숫자 {n}" for n in sorted(_numbers(body) - allowed)]
    return r + text_reasons(text) + semantic_reasons(body)


CITE_RE = re.compile(r"\s*\[[a-z_]+:\d+\]")
DANGLING_RE = re.compile(r"(?:에\s*따라|에\s*의해|에\s*근거해|를\s*바탕으로)[\s.,]*$|^[\s.,]*(?:에\s*따라|에\s*의해)")


def clean_llm_text(text: str) -> str:
    """LLM 글에서 인용 꼬리표를 지우고 남은 찌꺼기(".,", ",,", "에 따라." 같은 토막, 겹친 쉼표·공백)를 정리."""
    t = CITE_RE.sub("", text)
    t = re.sub(r"\s+([,.])", r"\1", t)
    t = re.sub(r"([.!?])\s*,+", r"\1", t)
    t = re.sub(r",(?:\s*,)+", ",", t)
    t = re.sub(r",\s*([.!?])", r"\1", t)
    t = re.sub(r"\.{2,}", ".", t)
    keep = [s.strip(" ,") for s in split_sentences(t)]
    keep = [s for s in keep if len(re.sub(r"[\W_]", "", s)) >= 2 and not DANGLING_RE.search(s)]
    return re.sub(r"[ \t]{2,}", " ", " ".join(keep)).strip().rstrip(",").strip()
