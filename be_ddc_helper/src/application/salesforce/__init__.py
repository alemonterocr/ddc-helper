"""Salesforce intake module.

Replaces manual GM Prebuild/BuySell data entry with a single SF Board URL.
The browser executes 4 UI API GETs against Salesforce (driven by the WS-RPC
bridge); this module parses the questionnaire blob, classifies Prebuild vs.
BuySell via LLM, and assembles a `DealerBundle`.

See `SALESFORCE_INTAKE_SDD.md` at repo root.
"""
