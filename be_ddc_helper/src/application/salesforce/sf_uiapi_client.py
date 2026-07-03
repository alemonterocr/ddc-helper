"""Backend-side UI API URL builder + WS-bridge dispatcher.

The backend decides which Salesforce paths to fetch; the browser executes them.
A single browser tool (`sf_ui_api_get`) takes a path string and returns the
parsed JSON body. This module owns the path-construction so the browser stays
generic.

See SDD §5.1 for the endpoint table and §5.1.1 for the rationale.
"""

from __future__ import annotations

from typing import Any

from src.adapters.outbound.browser_bridge.ws_bridge_adapter import WsBridgeAdapter

# Public UI API version. Bump when SF deprecates older versions.
_API = "/services/data/v66.0/ui-api"

_QUESTIONNAIRE_NAME = "DDC Client Onboarding Questionnaire"


# ── URL builders (pure) ────────────────────────────────────────────────────


def path_related_list_insights(board_id: str) -> str:
    """Step 1: list Insights related to the Board record."""
    fields = ",".join([
        "taskfeed1__Board_Insight__c.Id",
        "taskfeed1__Board_Insight__c.Name",
    ])
    return f"{_API}/related-list-records/{board_id}/taskfeed1__Board_Insights__r?fields={fields}&pageSize=10"


def path_record_questionnaire(insight_id: str) -> str:
    """Step 2: read the Insight record (gets Description__c)."""
    fields = ",".join([
        "taskfeed1__Board_Insight__c.taskfeed1__Description__c",
        "taskfeed1__Board_Insight__c.Name",
    ])
    return f"{_API}/records/{insight_id}?fields={fields}"


def path_record_board(board_id: str) -> str:
    """Step 3: read the Board record (gets psx__Project__c)."""
    fields = ",".join([
        "taskfeed1__Board__c.psx__Project__c",
        "taskfeed1__Board__c.Name",
        "taskfeed1__Board__c.taskfeed1__Type__c",
    ])
    return f"{_API}/records/{board_id}?fields={fields}"


def path_record_precursive_project(project_id: str) -> str:
    """Step 4: read the Precursive Project (gets Project_ID__c + dealer id)."""
    fields = ",".join([
        "preempt__PrecursiveProject__c.Project_ID__c",
        "preempt__PrecursiveProject__c.Product_Fulfillment_Account__r.Name",
        "preempt__PrecursiveProject__c.Name",
    ])
    return f"{_API}/records/{project_id}?fields={fields}"


# ── Bridge dispatcher ──────────────────────────────────────────────────────


class SfApiError(RuntimeError):
    """Raised when the browser-side fetch returns non-200 or no result."""


async def ui_api_get(bridge: WsBridgeAdapter, ws_session_id: str, path: str) -> dict[str, Any]:
    """Dispatch one UI API GET via the WS bridge. Returns the parsed JSON body.

    ws_session_id is the routing key the FE used to open the WebSocket
    (typically the board_id for intake - see ws_handler).
    """
    result = await bridge.call_tool(
        ws_session_id,
        "sf_ui_api_get",
        {"path": path},
    )
    if not result.get("ok"):
        raise SfApiError(result.get("error") or "sf_ui_api_get returned ok=false")
    body = result.get("result")
    if not isinstance(body, dict):
        raise SfApiError(f"sf_ui_api_get returned non-dict body: {type(body).__name__}")
    if "status" in body and body["status"] != 200:
        raise SfApiError(f"UI API HTTP {body['status']} for {path}")
    payload = body.get("body")
    if not isinstance(payload, dict):
        raise SfApiError(f"sf_ui_api_get body field missing or not a dict for {path}")
    return payload


# ── Field-extraction helpers (pure) ────────────────────────────────────────


def extract_questionnaire_insight_id(related_list_body: dict[str, Any]) -> str | None:
    """From step 1 body, pick the Insight Id (preferring the canonical name)."""
    records = related_list_body.get("records", []) or []
    if not records:
        return None
    # Prefer the one named "DDC Client Onboarding Questionnaire"; fall back to first.
    onboarding = next(
        (r for r in records if _field_value(r, "Name") == _QUESTIONNAIRE_NAME),
        None,
    )
    chosen = onboarding or records[0]
    val = _field_value(chosen, "Id")
    return val if isinstance(val, str) else None


def extract_questionnaire_text(record_body: dict[str, Any]) -> str | None:
    val = _field_value(record_body, "taskfeed1__Description__c")
    return val if isinstance(val, str) else None


def extract_precursive_project_id(record_body: dict[str, Any]) -> str | None:
    val = _field_value(record_body, "psx__Project__c")
    return val if isinstance(val, str) else None


def extract_ppr_and_dealer(record_body: dict[str, Any]) -> tuple[str | None, str | None]:
    """Returns (ppr, dealer_id). dealer_id has the `DDC-` prefix stripped."""
    ppr = _field_value(record_body, "Project_ID__c")
    ppr_str = ppr if isinstance(ppr, str) else None

    # Nested reference: Product_Fulfillment_Account__r.value.fields.Name.value
    fields = record_body.get("fields") or {}
    pfa = (fields.get("Product_Fulfillment_Account__r") or {}).get("value")
    name = None
    if isinstance(pfa, dict):
        name_field = (pfa.get("fields") or {}).get("Name") or {}
        name = name_field.get("value")
    dealer_id = None
    if isinstance(name, str):
        dealer_id = name[len("DDC-"):] if name.startswith("DDC-") else name

    return ppr_str, dealer_id


def _field_value(record: dict[str, Any], field_name: str) -> Any:
    """UI API records nest values under `fields.<name>.value`."""
    fields = record.get("fields") or {}
    entry = fields.get(field_name) or {}
    return entry.get("value")
