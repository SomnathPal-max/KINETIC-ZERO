"""
M0 Acceptance Test: Validates contracts, Pydantic schemas, and example JSON files.
"""

import os
import json
import pytest
from contracts.models import (
    InvoiceExtraction,
    AgentProposal,
    GuardReport,
    Workflow,
    HealEvent,
    RunLog,
)

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "contracts", "examples")


def test_invoice_extraction_example():
    path = os.path.join(EXAMPLES_DIR, "invoice_extraction.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    model = InvoiceExtraction.model_validate(data)
    assert model.doc_id == "inv_001"
    assert model.fields.vendor_gstin.value == "27AAPFU0939F1ZV"
    assert len(model.line_items) == 1


def test_agent_proposal_example():
    path = os.path.join(EXAMPLES_DIR, "agent_proposal.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    model = AgentProposal.model_validate(data)
    assert model.decision == "APPROVE"
    assert len(model.claims) == 2


def test_guard_report_example():
    path = os.path.join(EXAMPLES_DIR, "guard_report.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    model = GuardReport.model_validate(data)
    assert model.verdict == "PROCEED"
    assert model.data_trust_score == 96
    assert len(model.claims) == 9


def test_workflow_example():
    path = os.path.join(EXAMPLES_DIR, "workflow.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    model = Workflow.model_validate(data)
    assert model.workflow_id == "wf_vendor_claim"
    assert len(model.steps) >= 12
    assert model.steps[-1].irreversible is True


def test_heal_event_example():
    path = os.path.join(EXAMPLES_DIR, "heal_event.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    model = HealEvent.model_validate(data)
    assert model.tier == 1
    assert model.score_top == 0.88
    assert model.margin == 0.56


def test_run_log_example():
    path = os.path.join(EXAMPLES_DIR, "run_log.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    model = RunLog.model_validate(data)
    assert model.outcome == "SUCCESS"
    assert len(model.steps) == 2


def test_health_endpoint():
    from app.main import health
    res = health()
    assert res["status"] == "ok"
    assert res["app"] == "KINETIC-ZERO"



def test_llm_disk_cache(tmp_path, monkeypatch):
    from app.llm import call_json, _compute_cache_key
    monkeypatch.setenv("K0_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("K0_OFFLINE", "0")

    prompt = "Test prompt"
    schema = {"type": "object", "properties": {"msg": {"type": "string"}}}
    key = _compute_cache_key("gemini-2.5-flash", prompt, schema, None)
    cache_file = tmp_path / f"test_{key}.json"

    # Pre-seed cache to simulate cached call
    cache_file.write_text(json.dumps({"_tokens": 10, "result": {"msg": "cached_success"}}), encoding="utf-8")

    res = call_json("test", prompt, schema)
    assert res == {"msg": "cached_success"}

