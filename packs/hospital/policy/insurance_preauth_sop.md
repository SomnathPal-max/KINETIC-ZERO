# Apollo-Care Healthcare Network - Patient Health Insurance Pre-Authorization Standard Operating Procedure (SOP)

### HP-1.1 Active Policy Status
The patient insurance policy number must hold an ACTIVE status in the Insurer Central Registry at the time of pre-authorization submission. Policies marked LAPSED, SUSPENDED, or TERMINATED are ineligible for cashless hospital admission and must be rejected immediately.

### HP-1.2 Idempotency and Duplicate Request
A cashless pre-authorization request for the same patient ID and proposed admission date cannot be submitted more than once. Duplicate requests are blocked to prevent fraudulent multi-billing.

### HP-2.1 Covered Diagnosis Codes
Cashless pre-authorization is authorized strictly for approved standard medical ICD-10 diagnosis categories:
- J18: Pneumonia / Severe Respiratory Infection
- K35: Acute Appendicitis / Abdominal Surgery
- M16: Osteoarthritis / Joint Replacement
- I20: Angina Pectoris / Ischemic Heart Disease
- S72: Fracture of Femur / Orthopedic Trauma
- E11: Type 2 Diabetes with Acute Complications
Non-therapeutic, elective cosmetic procedures (ICD code Z41), unlisted experimental treatments, or routine checkups are strictly excluded from cashless authorization and are blocked.

### HP-3.1 Standard Pre-Auth Approval Limit
Pre-authorization requests with an estimated procedure cost up to Rs 50,000 may be auto-approved for immediate cashless admission when all other validation checks pass.

### HP-3.2 Medical Director Review Threshold
Pre-authorization requests with an estimated procedure cost between Rs 50,001 and Rs 200,000 exceed the automated clerk threshold and require formal review and escalation to the Medical Director before portal submission.

### HP-3.3 Policy Coverage Ceiling
Pre-authorization requests exceeding Rs 200,000 exceed the standard portal limit and must be rejected for offline corporate underwriter evaluation.

### HP-4.1 Empanelled Hospital Network
The treating medical facility (hospital_id) must be an active, credentialed facility within the insurer's Empanelled Cashless Provider Network. Facilities with expired or non-network credentials are rejected for cashless admission.

### HP-5.1 Admission Date Window
The proposed hospital admission date must fall within 30 days from today and cannot be a past date.

### HP-5.2 Source Evidence Grounding
Every critical field submitted to the insurance portal (patient name, patient ID, policy number, diagnosis code, hospital ID, estimated cost) must be traceable with high semantic fidelity to the uploaded hospital intake document. Ungrounded or hallucinated fields trigger immediate escalation or block.
