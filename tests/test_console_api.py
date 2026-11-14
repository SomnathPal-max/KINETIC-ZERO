"""
Unit Tests for Console UI Backend APIs.
Validates all routes in app/main.py.
"""

import os
import json
import pytest
from app.main import (
    health,
    get_console,
    list_demo_invoices,
    get_invoice_details,
    run_preflight,
    inject_hallucination,
    list_workflows,
    get_workflow_details,
    execute_run,
    get_bench_results,
    confirm_pending_run,
    pending_confirmations,
)


def test_health():
    res = health()
    assert res["status"] == "ok"


def test_console_html_rendering():
    res = get_console()
    assert res.status_code == 200
    assert "KINETIC-ZERO Console" in res.body.decode("utf-8")


def test_invoices_api():
    demos = list_demo_invoices()
    assert len(demos) >= 4
    assert any(d["id"] == "demo_clean" for d in demos)

    inv = get_invoice_details("demo_clean")
    assert inv["doc_id"] == "demo_clean"
    assert inv["guard"]["verdict"] == "PROCEED"
    assert inv["guard"]["data_trust_score"] >= 80


def test_preflight_api():
    suite = run_preflight({"doc_id": "demo_clean"})
    assert suite["total_variants"] == 7
    assert suite["blocked_variants"] == 7
    assert suite["all_blocked"] is True
    assert len(suite["variants"]) == 7
    # All counterfactual perturbations must be blocked
    assert all(item["passed"] is True for item in suite["variants"])


def test_inject_hallucination_api():
    res = inject_hallucination({
        "doc_id": "demo_clean",
        "field": "total",
        "bogus_value": "99999.00",
    })
    # Must trip G9 Grounding and set ai_overruled to True
    assert res["guard"]["verdict"] == "BLOCK"
    assert "G9" in res["guard"]["failed_gates"]
    assert res["guard"]["ai_overruled"] is True


def test_workflows_api():
    wfs = list_workflows()
    assert len(wfs) >= 1
    assert wfs[0]["workflow_id"] == "wf_vendor_claim"

    wf = get_workflow_details("wf_vendor_claim")
    assert len(wf["steps"]) == 12
    # Verify Step Fragility Forecast (F11)
    assert "fragility" in wf["steps"][0]
    assert wf["steps"][0]["fragility"]["level"] in ["LOW", "MED", "HIGH"]


def test_run_api_and_human_confirm():
    # 1. Run with auto_confirm_human=False
    run_res = execute_run({
        "workflow_id": "wf_vendor_claim",
        "doc_id": "demo_clean",
        "mode": "k0_full",
        "mutation": "M6",
        "auto_confirm_human": False,
    })
    assert run_res["outcome"] == "ESCALATED"
    run_id = run_res["run_id"]
    assert run_id in pending_confirmations

    # 2. Confirm pending run
    confirm_res = confirm_pending_run(run_id, {"approved": True})
    assert confirm_res["status"] == "SUBMITTED"
    assert confirm_res["outcome"] == "SUCCESS"


def test_bench_results_api():
    res = get_bench_results()
    assert "guard_benchmark" in res
    assert "heal_benchmark" in res
    assert res["guard_benchmark"]["n_invoices"] >= 60
