"""설정: 환경변수와 harness.yaml 읽기."""
import json
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]  # masdae-market/
HARNESS_YAML = ROOT / "harness" / "harness.yaml"
WASTE_CODES_JSON = ROOT / "data" / "waste_codes.json"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./masdae.db")


@lru_cache
def harness_config() -> dict:
    return yaml.safe_load(HARNESS_YAML.read_text(encoding="utf-8"))


@lru_cache
def waste_names() -> dict:
    data = json.loads(WASTE_CODES_JSON.read_text(encoding="utf-8"))
    return {w["code"]: w["name"] for w in data}


def llm_info() -> dict:
    cfg = harness_config()["llm"]
    provider = os.environ.get("LLM_PROVIDER", cfg["provider"])
    model = (cfg.get(provider) or {}).get("model", "") if provider != "off" else ""
    return {"provider": provider, "model": model, "available": provider != "off"}
