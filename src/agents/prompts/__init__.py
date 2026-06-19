"""Agent prompts package — loaded from .txt files at module level."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load(name: str) -> str:
    """Load a prompt file by name (without .txt extension)."""
    return (_PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()


# ── Pre-loaded prompts ──────────────────────────────────────────────
SUPERVISOR_PROMPT = _load("supervisor_prompt")
ANALYTICAL_PROMPT = _load("analytical_prompt")
CX_PROMPT = _load("cx_prompt")
INTERNAL_OPS_PROMPT = _load("internal_ops_prompt")
GENERAL_PROMPT = _load("general_prompt")
PRICING_PROMPT = _load("pricing_prompt")
SUPPLY_CHAIN_PROMPT = _load("supply_chain_prompt")
