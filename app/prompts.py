"""
Prompt templates for KINETIC-ZERO.
Follows SPEC.txt Appendix B. All use JSON output and temperature 0.
"""

INVOICE_EXTRACTION_PROMPT = """SYSTEM: You extract fields from a vendor invoice. Use ONLY the text provided. Never infer or
guess. If a field is absent return value "" and evidence "". For every non-empty field,
`evidence` MUST be a verbatim snippet copied from the text that contains the value.
Money values: digits and decimal point only, no currency symbol or commas.
Dates: ISO YYYY-MM-DD.
USER: <document_text>{source_text}</document_text>
Return JSON matching the InvoiceExtraction.fields and line_items schema."""

AGENT_PROPOSAL_PROMPT = """SYSTEM: You are a payment-processing assistant. Decide APPROVE, HOLD or REJECT for this invoice
using ONLY the extracted fields and the policy clauses given. Each claim you make must cite a
clause_id from the provided clauses and list any numbers you rely on in quoted_numbers.
Do not cite a clause that is not provided.
USER: <fields>{fields_json}</fields> <clauses>{top_k_clauses_with_ids}</clauses>
Return JSON matching AgentProposal."""

HEAL_SELECTION_PROMPT = """SYSTEM: You repair a broken web automation step. Pick the candidate element that matches the
step intent. If none clearly matches, return choice null. Never pick an element whose text
suggests cancel, delete, reject, back or clear unless the intent says so.
USER: intent: {intent}   action: {action}   page: {url} | {title}
recorded_element: {recorded_fingerprint_compact}
candidates: {candidates_json}
Return JSON {{"choice": <int or null>, "confidence": <0-1>, "reason": "<one sentence>"}}"""

STEP_INTENT_PROMPT = """SYSTEM: For each recorded step write a short imperative intent (max 8 words). Use the
narration if present, else the label/text. Return a JSON list aligned with the input order."""
