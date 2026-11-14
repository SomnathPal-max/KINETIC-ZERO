# Conflicts Log

This file logs any conflicts between prompts/ideas and the frozen specification `docs/SPEC.txt` (as required by Rule 1).

## 2026-11-14 (KINETIC-ZERO v2 Domain Pack Decoupling)
- **Topic:** Gate G1-G7 modularization vs Universal TruthGuard.
- **Resolution:** G1-G7 are formalized as the rule set for the `finance` domain pack. The core TruthGuard executes universal checks (G9 Substring Grounding, G8 Citation Verification, G6 Duplicate Key / Idempotency, Required Field Presence) and dynamically evaluates pack-specific rule definitions (`rules.json` and custom validators). This satisfies both the frozen spec and the v2 modular Domain Pack architecture.
