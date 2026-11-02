
import pytest

from app.harness.runner import run_flow
from app.llm import get_provider

pytestmark = pytest.mark.live


def test_ollama_live_grade_bag():
    llm = get_provider("ollama")
    if not llm.reachable():
        pytest.skip(f"Ollama 연결 불가: {llm.url}")
    r = run_flow("grade_bag", {"bag": {"target_material": "pp", "note": "PP 사출 스프루",
                                       "items": [{"material": "pp", "kg": 97}, {"material": "pe", "kg": 3}]}}, llm=llm)
    print("\nLIVE", r.llm, r.summary_source, r.blocked_count, repr(r.summary), [e.payload for e in r.events if e.type == "gate"])
    assert r.results[1].data["grade"]["grade"] == "A"       # 등급은 코드 값
    assert r.llm["provider"] == "ollama"
    assert r.summary_source in ("llm", "template")
