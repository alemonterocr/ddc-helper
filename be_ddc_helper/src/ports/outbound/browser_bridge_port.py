from typing import Protocol

from src.domain.models import SectionCommand, SectionResult


class BrowserBridgePort(Protocol):
    async def execute_section(self, command: SectionCommand) -> SectionResult: ...
