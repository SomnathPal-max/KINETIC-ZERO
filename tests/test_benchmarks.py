"""
Tests for Milestone M4 Benchmark Results.
Validates bench/results.json matches schema and acceptance criteria.
"""

import os
import json
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_PATH = os.path.join(ROOT_DIR, "bench", "results.json")


def test_results_json_exists():
    assert os.path.exists(RESULTS_PATH), "bench/results.json must exist"


def test_results_schema_and_values():
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Top-level metadata
    assert "generated_at" in data
    assert "git_commit" in data
    assert "guard_benchmark" in data
    assert "heal_benchmark" in data

    # Guard Benchmark checks
    gb = data["guard_benchmark"]
    assert gb["n_invoices"] >= 60
    assert gb["false_block_rate_pct"] == 0.0
    assert gb["hallucination_catch_rate_pct"] >= 95.0
    assert gb["citation_catch_rate_pct"] >= 95.0

    # Every injected fault type must have high recall
    for fault, recall in gb["fault_recall_pct"].items():
        assert recall >= 90.0, f"Recall for {fault} was {recall}%"

    # Heal Benchmark checks
    hb = data["heal_benchmark"]
    methods = hb["methods"]
    assert "baseline" in methods
    assert "k0_tier1" in methods
    assert "k0_full" in methods

    # Baseline fails under mutation
    assert methods["baseline"]["success_pct"] == 0.0
    assert methods["baseline"]["crash_pct"] > 0.0 or methods["baseline"]["wrong_action_pct"] > 0.0

    # Self-healing succeeds under mutation
    assert methods["k0_tier1"]["success_pct"] >= 95.0
    assert methods["k0_tier1"]["wrong_action_pct"] == 0.0

    assert methods["k0_full"]["success_pct"] >= 95.0
    assert methods["k0_full"]["wrong_action_pct"] == 0.0

    # Memory experiment
    mem = hb["memory_experiment"]
    assert mem["memory_hit_ratio_pct"] == 100.0
    assert mem["second_run_llm_calls"] == 0
