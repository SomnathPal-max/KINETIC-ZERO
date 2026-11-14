"""
Heal Benchmark Suite for KINETIC-ZERO.
Follows SPEC.txt Section 6.8.
Evaluates:
- Mutations M1-M6 x 5 seeds = 30 trials per method (baseline, k0_tier1, k0_full)
- Measures success %, wrong-action %, escalated %, crash %, mean LLM calls, mean latency (ms)
- Runs memory experiment (2nd run after heal = 0 LLM calls)
- Outputs bench/results.json
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import json
import time
from contracts.models import InvoiceExtraction, InvoiceFields, FieldExtraction, LineItem
from app.recorder import load_workflow
from app.runner import runner
from app.portal.routes import api_reset_portal, set_mutation
from app.memory import clear_memory
from bench.guard_bench import run_guard_benchmark

RESULTS_PATH = os.path.join(ROOT_DIR, "bench", "results.json")


def get_benchmark_invoice() -> InvoiceExtraction:
    return InvoiceExtraction(
        doc_id="bench_clean",
        source_type="pdf_text",
        passes=1,
        source_text="Apex Industrial Supplies 27AAPFU0939F1ZV 27AAAPL1234F1Z8 INV-BENCH-01 2026-11-01 1000.00 90.00 90.00 0.00 1180.00",
        fields=InvoiceFields(
            vendor_name=FieldExtraction(value="Apex Industrial Supplies", evidence="Apex Industrial Supplies"),
            vendor_gstin=FieldExtraction(value="27AAPFU0939F1ZV", evidence="27AAPFU0939F1ZV"),
            buyer_gstin=FieldExtraction(value="27AAAPL1234F1Z8", evidence="27AAAPL1234F1Z8"),
            invoice_no=FieldExtraction(value="INV-BENCH-01", evidence="INV-BENCH-01"),
            invoice_date=FieldExtraction(value="2026-11-01", evidence="2026-11-01"),
            po_number=FieldExtraction(value="PO-1", evidence="PO-1"),
            taxable_value=FieldExtraction(value="1000.00", evidence="1000.00"),
            cgst=FieldExtraction(value="90.00", evidence="90.00"),
            sgst=FieldExtraction(value="90.00", evidence="90.00"),
            igst=FieldExtraction(value="0.00", evidence="0.00"),
            total=FieldExtraction(value="1180.00", evidence="1180.00"),
        ),
        line_items=[LineItem(desc="Bearing", qty="10", rate="100.00", amount="1000.00")],
    )


def run_heal_benchmark() -> dict:
    wf = load_workflow("wf_vendor_claim")
    inv = get_benchmark_invoice()
    mutations = ["M1", "M2", "M3", "M4", "M5", "M6"]
    seeds = [1, 2, 3, 4, 5]

    methods = ["baseline", "k0_tier1", "k0_full"]
    metrics = {}

    for method in methods:
        clear_memory()
        successes = 0
        wrong_actions = 0
        crashes = 0
        escalations = 0
        total_llm_calls = 0
        total_latency_ms = 0
        runs_count = 0

        for m in mutations:
            for s in seeds:
                api_reset_portal()
                set_mutation({"type": m, "seed": s})
                runs_count += 1

                log = runner.run_workflow(wf, inv, mode=method, mutation=m, auto_confirm_human=True)
                if log.outcome == "SUCCESS":
                    successes += 1
                elif log.outcome == "WRONG_ACTION":
                    wrong_actions += 1
                elif log.outcome == "CRASH":
                    crashes += 1
                elif log.outcome == "ESCALATED":
                    escalations += 1

                total_llm_calls += log.llm_calls
                total_latency_ms += log.total_ms

        metrics[method] = {
            "runs": runs_count,
            "success_pct": round((successes / runs_count) * 100.0, 1),
            "wrong_action_pct": round((wrong_actions / runs_count) * 100.0, 1),
            "escalated_pct": round((escalations / runs_count) * 100.0, 1),
            "crash_pct": round((crashes / runs_count) * 100.0, 1),
            "mean_llm_calls": round(total_llm_calls / runs_count, 2),
            "mean_latency_ms": round(total_latency_ms / runs_count, 1),
        }

    # --- Memory Cache Experiment ---
    # First heal under M6, then rerun under same mutation
    api_reset_portal()
    set_mutation({"type": "M6", "seed": 42})
    log_first = runner.run_workflow(wf, inv, mode="k0_full", mutation="M6", auto_confirm_human=True)
    first_llm_calls = log_first.llm_calls

    api_reset_portal()
    set_mutation({"type": "M6", "seed": 42})
    log_second = runner.run_workflow(wf, inv, mode="k0_full", mutation="M6", auto_confirm_human=True)
    second_llm_calls = log_second.llm_calls

    memory_experiment = {
        "mutation": "M6",
        "first_run_llm_calls": first_llm_calls,
        "second_run_llm_calls": second_llm_calls,
        "memory_hit_ratio_pct": 100.0 if second_llm_calls == 0 else 0.0,
    }

    return {
        "methods": metrics,
        "memory_experiment": memory_experiment,
    }


def generate_full_results():
    print("Running Guard Benchmark...")
    guard_res = run_guard_benchmark()

    print("Running Heal Benchmark (30 trials x 3 methods)...")
    heal_res = run_heal_benchmark()

    import subprocess
    git_hash = "head"
    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        git_hash = "k0_frozen_v1"

    full_results = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_hash,
        "guard_benchmark": guard_res,
        "heal_benchmark": heal_res,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)

    print(f"\nAll benchmark results successfully written to {RESULTS_PATH}")
    return full_results


if __name__ == "__main__":
    generate_full_results()
