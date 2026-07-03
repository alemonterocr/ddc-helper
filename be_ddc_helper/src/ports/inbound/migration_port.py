from typing import Protocol

from src.domain.models import DOMSkeleton, LLMProvider, SectionPlan


class MigrationPort(Protocol):
    async def analyze_page(
        self,
        skeleton: DOMSkeleton,
        dealer_id: str,
        provider: LLMProvider,
    ) -> SectionPlan: ...
