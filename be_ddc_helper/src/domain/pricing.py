"""Per-provider, per-model token pricing.

All rates are USD per 1,000,000 tokens. Sourced from each provider's published
pricing as of 2026-06-08. Update when provider rates change.

Lookup is by (provider, model) tuple, case-sensitive on both. Returns None when
a model is missing — callers should treat as $0 and log a warning rather than
crashing.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenRate:
    input_per_million: float
    output_per_million: float


# (provider, model) → rate
PRICING: dict[tuple[str, str], TokenRate] = {
    # ── Anthropic ───────────────────────────────────────────────────────────
    ("anthropic", "claude-sonnet-4-5"):   TokenRate(3.00, 15.00),
    ("anthropic", "claude-opus-4-7"):     TokenRate(15.00, 75.00),
    ("anthropic", "claude-haiku-4-5"):    TokenRate(1.00, 5.00),

    # ── DeepSeek ────────────────────────────────────────────────────────────
    ("deepseek", "deepseek-chat"):        TokenRate(0.27, 1.10),
    ("deepseek", "deepseek-reasoner"):    TokenRate(0.55, 2.19),

    # ── Gemini ──────────────────────────────────────────────────────────────
    ("gemini", "gemini-2.0-flash"):       TokenRate(0.10, 0.40),
    ("gemini", "gemini-2.5-pro"):         TokenRate(1.25, 5.00),
}


def lookup_rate(provider: str, model: str) -> TokenRate | None:
    return PRICING.get((provider, model))


def cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a single LLM call.

    Returns 0.0 when the (provider, model) pair is not in the pricing table —
    safe default that won't crash the pipeline; the discrepancy will surface
    as $0.00 for that stage in the response.
    """
    rate = lookup_rate(provider, model)
    if rate is None:
        return 0.0
    return (
        (input_tokens / 1_000_000) * rate.input_per_million
        + (output_tokens / 1_000_000) * rate.output_per_million
    )
