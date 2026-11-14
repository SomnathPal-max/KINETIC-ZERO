# Contract Changes Log

This file logs any optional fields added to frozen contracts in `contracts/models.py` (as required by Rule 5).
Fields are never renamed or removed.

## 2026-11-14 (KINETIC-ZERO v2 Domain Pack Generalization)
1. Added optional fields to `InvoiceExtraction`:
   - `pack_id: Optional[str] = "finance"`
   - `doc_type: Optional[str] = "invoice"`
2. Added `HospitalFields` and `HospitalExtraction` models for Hospital Pack (Insurance Pre-Authorization).
   - Preserves 100% backward compatibility with frozen `InvoiceExtraction` and `AgentProposal` contracts.
