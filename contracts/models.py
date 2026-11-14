"""
Frozen Data Contracts for KINETIC-ZERO.
Follows SPEC.txt Section 5 exactly.
"""

from typing import Literal, Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


# --- Section 5.1: InvoiceExtraction ---

class FieldExtraction(BaseModel):
    value: str = ""
    evidence: str = ""
    pass2_value: Optional[str] = None


class LineItem(BaseModel):
    desc: str
    qty: str
    rate: str
    amount: str


class InvoiceFields(BaseModel):
    vendor_name: FieldExtraction = Field(default_factory=FieldExtraction)
    vendor_gstin: FieldExtraction = Field(default_factory=FieldExtraction)
    buyer_gstin: FieldExtraction = Field(default_factory=FieldExtraction)
    invoice_no: FieldExtraction = Field(default_factory=FieldExtraction)
    invoice_date: FieldExtraction = Field(default_factory=FieldExtraction)
    po_number: FieldExtraction = Field(default_factory=FieldExtraction)
    taxable_value: FieldExtraction = Field(default_factory=FieldExtraction)
    cgst: FieldExtraction = Field(default_factory=FieldExtraction)
    sgst: FieldExtraction = Field(default_factory=FieldExtraction)
    igst: FieldExtraction = Field(default_factory=FieldExtraction)
    total: FieldExtraction = Field(default_factory=FieldExtraction)


class InvoiceExtraction(BaseModel):
    doc_id: str
    source_type: Literal["pdf_text", "image"] = "pdf_text"
    passes: Literal[1, 2] = 1
    source_text: str
    fields: InvoiceFields
    line_items: List[LineItem] = Field(default_factory=list)
    pack_id: Optional[str] = "finance"
    doc_type: Optional[str] = "invoice"


class HospitalFields(BaseModel):
    patient_name: FieldExtraction = Field(default_factory=FieldExtraction)
    patient_id: FieldExtraction = Field(default_factory=FieldExtraction)
    policy_number: FieldExtraction = Field(default_factory=FieldExtraction)
    insurer_id: FieldExtraction = Field(default_factory=FieldExtraction)
    diagnosis_code: FieldExtraction = Field(default_factory=FieldExtraction)
    treatment_type: FieldExtraction = Field(default_factory=FieldExtraction)
    hospital_id: FieldExtraction = Field(default_factory=FieldExtraction)
    admission_date: FieldExtraction = Field(default_factory=FieldExtraction)
    estimated_cost: FieldExtraction = Field(default_factory=FieldExtraction)


class HospitalExtraction(BaseModel):
    doc_id: str
    source_type: Literal["pdf_text", "image"] = "pdf_text"
    passes: Literal[1, 2] = 1
    source_text: str
    fields: HospitalFields
    pack_id: Optional[str] = "hospital"
    doc_type: Optional[str] = "preauth_form"


# --- Section 5.2: AgentProposal ---

class ProposalClaim(BaseModel):
    text: str
    clause_id: str
    quoted_numbers: List[str] = Field(default_factory=list)


class AgentProposal(BaseModel):
    doc_id: str
    decision: Literal["APPROVE", "HOLD", "REJECT"]
    claims: List[ProposalClaim] = Field(default_factory=list)


# --- Section 5.3: GuardReport ---

class GuardClaim(BaseModel):
    id: str
    statement: str
    kind: Literal["hard", "soft"]
    gate: Optional[str] = None
    status: Literal["PASS", "FAIL", "ESCALATE", "UNSUPPORTED"]
    evidence: str = ""
    clause_id: Optional[str] = None


class TrustComponents(BaseModel):
    S: float = Field(default=0.0, ge=0.0, le=1.0)
    A: float = Field(default=0.0, ge=0.0, le=1.0)
    P: float = Field(default=0.0, ge=0.0, le=1.0)


class GuardReport(BaseModel):
    doc_id: str
    verdict: Literal["PROCEED", "ESCALATE", "BLOCK"]
    data_trust_score: int = Field(default=0, ge=0, le=100)
    components: TrustComponents = Field(default_factory=TrustComponents)
    ai_overruled: bool = False
    claims: List[GuardClaim] = Field(default_factory=list)
    failed_gates: List[str] = Field(default_factory=list)
    explanation: str = ""


# --- Section 5.4: Workflow and Step ---

class Locator(BaseModel):
    strategy: Literal["testid", "id", "name", "role", "css"]
    value: str


class Fingerprint(BaseModel):
    tag: str = ""
    id: str = ""
    name: str = ""
    classes: List[str] = Field(default_factory=list)
    text: str = ""
    aria_label: str = ""
    role: str = ""
    type: str = ""
    placeholder: str = ""
    label_text: str = ""
    nearby_text: str = ""
    dom_path: str = ""
    bbox: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])  # [x, y, w, h] 0-1 viewport relative
    form_id: str = ""
    index_in_form: int = 0


class ExpectCondition(BaseModel):
    kind: Literal["value_equals", "url_contains", "text_visible", "element_visible"]
    arg: str


class WorkflowStep(BaseModel):
    id: str
    action: Literal["fill", "click", "select"]
    intent: str
    value_from: Optional[str] = None
    literal: Optional[str] = None
    irreversible: bool = False
    negative_terms: List[str] = Field(default_factory=lambda: ["cancel", "clear", "back"])
    locator: Locator
    alt_locators: List[Locator] = Field(default_factory=list)
    fingerprint: Fingerprint = Field(default_factory=Fingerprint)
    expect: Optional[ExpectCondition] = None
    screenshot: Optional[str] = None
    narration: Optional[str] = None


class Workflow(BaseModel):
    workflow_id: str
    name: str
    version: int = 1
    start_url: str = "/portal/claim"
    steps: List[WorkflowStep] = Field(default_factory=list)


# --- Section 5.5: HealEvent and RunLog ---

class HealEvent(BaseModel):
    run_id: str
    step_id: str
    tier: Literal[0, 1, 2, 3]  # 3 = memory cache hit
    old_locator: Locator
    new_locator: Locator
    score_top: float
    score_second: float
    margin: float
    llm_calls: int = 0
    latency_ms: int = 0
    verified: bool = True
    human_confirmed: Optional[bool] = None
    old_fp: Fingerprint
    new_fp: Fingerprint


class StepLog(BaseModel):
    step_id: str
    status: Literal["ok", "healed", "escalated", "failed"]
    tier: Optional[int] = None
    latency_ms: int = 0
    heal: Optional[HealEvent] = None
    screenshot: Optional[str] = None


class RunLog(BaseModel):
    run_id: str
    workflow_id: str
    mode: Literal["baseline", "k0_tier1", "k0_full"]
    mutation: Optional[Literal["M1", "M2", "M3", "M4", "M5", "M6"]] = None
    guard: Optional[GuardReport] = None
    steps: List[StepLog] = Field(default_factory=list)
    outcome: Literal["SUCCESS", "WRONG_ACTION", "CRASH", "ESCALATED", "BLOCKED"]
    llm_calls: int = 0
    tokens: int = 0
    total_ms: int = 0
