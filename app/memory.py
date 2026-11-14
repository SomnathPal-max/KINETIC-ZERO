"""
Episodic Memory Cache for Self-Healing (Tier 3).
SQLite storage in data/k0.db.
Follows SPEC.txt Section 4, 6.6.
"""

import os
import json
import sqlite3
import time
from typing import Optional, Dict, Any, Tuple
from contracts.models import Locator, Fingerprint, HealEvent

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "data", "k0.db")

_cached_conn: Optional[sqlite3.Connection] = None
_db_initialized = False


def get_db_connection() -> sqlite3.Connection:
    global _cached_conn
    if _cached_conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = sqlite3.Row
        _cached_conn = conn
    return _cached_conn


def init_db():
    global _db_initialized
    if _db_initialized:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS memory_patches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workflow_id TEXT NOT NULL,
        step_id TEXT NOT NULL,
        page_signature TEXT NOT NULL,
        locator_strategy TEXT NOT NULL,
        locator_value TEXT NOT NULL,
        fingerprint_json TEXT NOT NULL,
        tier INTEGER NOT NULL,
        created_at REAL NOT NULL,
        UNIQUE(workflow_id, step_id, page_signature)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS heal_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        step_id TEXT NOT NULL,
        tier INTEGER NOT NULL,
        old_locator TEXT NOT NULL,
        new_locator TEXT NOT NULL,
        score_top REAL,
        margin REAL,
        verified INTEGER NOT NULL,
        latency_ms INTEGER,
        created_at REAL NOT NULL
    )
    """)
    conn.commit()
    _db_initialized = True


def store_patch(
    workflow_id: str,
    step_id: str,
    page_signature: str,
    locator: Locator,
    fingerprint: Fingerprint,
    tier: int,
):
    """Saves verified healed patch to Tier 3 episodic memory."""
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO memory_patches (
        workflow_id, step_id, page_signature, locator_strategy, locator_value, fingerprint_json, tier, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(workflow_id, step_id, page_signature) DO UPDATE SET
        locator_strategy=excluded.locator_strategy,
        locator_value=excluded.locator_value,
        fingerprint_json=excluded.fingerprint_json,
        tier=excluded.tier,
        created_at=excluded.created_at
    """, (
        workflow_id,
        step_id,
        page_signature,
        locator.strategy,
        locator.value,
        json.dumps(fingerprint.model_dump()),
        tier,
        time.time(),
    ))
    conn.commit()


def lookup_patch(
    workflow_id: str,
    step_id: str,
    page_signature: str,
) -> Optional[Tuple[Locator, Fingerprint]]:
    """Looks up previously learned patch. Returns (Locator, Fingerprint) or None."""
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT locator_strategy, locator_value, fingerprint_json
    FROM memory_patches
    WHERE workflow_id = ? AND step_id = ? AND page_signature = ?
    """, (workflow_id, step_id, page_signature))
    row = cur.fetchone()

    if not row:
        return None

    loc = Locator(strategy=row["locator_strategy"], value=row["locator_value"])
    fp_dict = json.loads(row["fingerprint_json"])
    fp = Fingerprint.model_validate(fp_dict)
    return loc, fp


def record_heal_event(heal: HealEvent):
    """Logs a heal event for audit reporting and benchmark metrics."""
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO heal_events (
        run_id, step_id, tier, old_locator, new_locator, score_top, margin, verified, latency_ms, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        heal.run_id,
        heal.step_id,
        heal.tier,
        f"{heal.old_locator.strategy}:{heal.old_locator.value}",
        f"{heal.new_locator.strategy}:{heal.new_locator.value}",
        heal.score_top,
        heal.margin,
        1 if heal.verified else 0,
        heal.latency_ms,
        time.time(),
    ))
    conn.commit()


def clear_memory():
    """Resets memory patches for clean benchmark runs."""
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM memory_patches")
    cur.execute("DELETE FROM heal_events")
    conn.commit()
