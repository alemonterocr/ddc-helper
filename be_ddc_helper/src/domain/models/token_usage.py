"""Token usage tracking models.

`TokenUsage` records one LLM call. `TokenInfo` aggregates a request's worth of
calls for the analyze response. Both are domain shapes; the inbound layer
re-exposes them via its own Pydantic DTOs if needed.
"""

from dataclasses import dataclass, field


@dataclass
class TokenUsage:
    """One LLM call's worth of usage."""
    provider: str
    model: str
    stage: str           # e.g. 'chrome_review' | 'typify' | 'image_split' | 'enrich'
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class TokenInfo:
    """Aggregate usage for a full analyze request."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_stage: list[TokenUsage] = field(default_factory=list)

    @classmethod
    def from_log(cls, log: list[TokenUsage]) -> "TokenInfo":
        return cls(
            total_input_tokens=sum(u.input_tokens for u in log),
            total_output_tokens=sum(u.output_tokens for u in log),
            total_cost_usd=sum(u.cost_usd for u in log),
            by_stage=list(log),
        )
