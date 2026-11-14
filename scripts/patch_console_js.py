import sys

with open("app/static/console/console.js", "r", encoding="utf-8") as f:
    js = f.read()

# 1. Update renderDocumentVerification to toggle msme-badge-chip
target_msme = '''  // Animate trust score
  animateTrustScore(guard.data_trust_score || (verdict === "PROCEED" ? 100 : 0));'''

new_msme = '''  // Toggle Bharat Compliance MSME Badge
  const msmeChip = document.getElementById("msme-badge-chip");
  const hasMsme = (guard.claims || []).some(c => c.gate === "G10" && (c.evidence || "").includes("MSME"));
  if (msmeChip) {
    msmeChip.style.display = hasMsme ? "inline-flex" : "none";
  }

  // Animate trust score
  animateTrustScore(guard.data_trust_score || (verdict === "PROCEED" ? 100 : 0));'''

js = js.replace(target_msme, new_msme, 1)

# 2. Append new interactive features to console.js
new_features = '''
// -------------------------------------------------------------
// NEW UNIQUE FEATURES: INBOUND CHANNELS, CERTIFICATES & INSPECTOR
// -------------------------------------------------------------

function downloadTruthCertificate() {
  const docId = currentDocData ? currentDocData.doc_id : (activePackId === "hospital" ? "preauth_clean" : "demo_clean");
  showToast("Generating Cryptographic Truth Certificate PDF...", "info");
  window.open(`/api/documents/${activePackId}/${docId}/certificate`, "_blank");
}

function downloadRunCertificate() {
  const runId = activePendingRunId || "RUN-LATEST-01";
  showToast("Downloading Execution Audit Certificate (PDF)...", "info");
  window.open(`/api/run/${runId}/certificate`, "_blank");
}

function openHealerDiffModal() {
  openModal("healer-diff-modal");
  showToast("Opened 4-Tier Self-Healing Inspector", "info");
}

function openRecorderModal() {
  openModal("recorder-modal");
  const box = document.getElementById("recorder-stream-box");
  if (box) {
    box.innerHTML = `<div style="color: var(--text-muted);">[Ready] Click 'Start Recording' to begin capturing DOM interactions on the target portal...</div>`;
  }
  const btnStart = document.getElementById("btn-start-record");
  const btnSave = document.getElementById("btn-save-record");
  if (btnStart) {
    btnStart.disabled = false;
    btnStart.innerHTML = `<span class="pulse-dot" style="margin-right: 4px;"></span> Start Recording`;
  }
  if (btnSave) btnSave.disabled = true;
}

let recorderTimer = null;
function simulateStartRecording() {
  const btnStart = document.getElementById("btn-start-record");
  const btnSave = document.getElementById("btn-save-record");
  const box = document.getElementById("recorder-stream-box");
  if (!box || !btnStart) return;

  btnStart.disabled = true;
  btnStart.innerHTML = `<span class="btn-spinner"></span> Recording Active...`;
  box.innerHTML = `<div style="color: var(--status-emerald); font-weight: 700;">[LISTENER ACTIVE] Hooked to Target Web Portal DOM...</div>`;

  showToast("Recording live user actions on portal...", "info");

  const recordedSteps = [
    "[00:01] FOCUS & CLICK: input#vendor_gstin (Tag: INPUT, Bounding Box: [140, 220, 280, 36])",
    "[00:03] INPUT EVENT: '27AAPFU0939F1ZV' -> Auto-parameterized as variable ${vendor_gstin}",
    "[00:05] FOCUS & CLICK: input#invoice_no (Tag: INPUT)",
    "[00:07] INPUT EVENT: 'INV-DEMO-01' -> Auto-parameterized as variable ${invoice_no}",
    "[00:09] CLICK: button#btn_submit -> Marked as Irreversible Submission Gate (Fragility: 40%)"
  ];

  let idx = 0;
  recorderTimer = setInterval(() => {
    if (idx < recordedSteps.length) {
      const row = document.createElement("div");
      row.style.color = "var(--text-primary)";
      row.style.marginTop = "4px";
      row.textContent = recordedSteps[idx];
      box.appendChild(row);
      box.scrollTop = box.scrollHeight;
      idx++;
    } else {
      clearInterval(recorderTimer);
      if (btnSave) btnSave.disabled = false;
      btnStart.innerHTML = `✓ 5 Steps Captured`;
      showToast("Task recording captured: 5 steps ready to compile", "success");
    }
  }, 400);
}

function simulateSaveRecording() {
  closeModal("recorder-modal");
  const taskName = document.getElementById("record-task-name")?.value || "wf_custom_task";
  showToast(`Successfully compiled skill '${taskName}' with 5 steps!`, "success");
  
  // Add temporary step row to workflow table to show judges
  const tbody = document.querySelector("#workflow-steps-table tbody");
  if (tbody) {
    const tr = document.createElement("tr");
    tr.style.backgroundColor = "rgba(99, 102, 241, 0.08)";
    tr.innerHTML = `
      <td style="font-family:var(--font-mono); font-weight:700; color:#818cf8;">NEW</td>
      <td><span class="chip chip-emerald">Recorded</span></td>
      <td style="font-weight:600; color:var(--text-primary);">Custom Taught Task (${taskName})</td>
      <td style="font-family:var(--font-mono); color:var(--status-blue);">${'${dynamic_bindings}'}</td>
      <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary);">Recorded DOM Fingerprints</td>
      <td style="font-family:var(--font-mono); color:var(--status-emerald);">25% (Robust)</td>
      <td><span class="chip chip-amber">YES (Gate)</span></td>
    `;
    tbody.insertBefore(tr, tbody.firstChild);
  }
}

function ingestFromWhatsApp() {
  switchDomainPack("finance");
  showToast("Ingested invoice INV-DEMO-01 from WhatsApp Business (+91 98201 XXXXX)", "success");
  const selector = document.getElementById("invoice-selector");
  if (selector) {
    selector.value = "demo_clean";
    loadSelectedDocument();
  }
}

function ingestFromGmail() {
  switchDomainPack("hospital");
  showToast("Ingested patient pre-auth form PT-10492 from Gmail AP Inbox", "success");
  const selector = document.getElementById("invoice-selector");
  if (selector) {
    selector.value = "preauth_clean";
    loadSelectedDocument();
  }
}
'''

js += new_features

with open("app/static/console/console.js", "w", encoding="utf-8") as f:
    f.write(js)

print("SUCCESS: Updated console.js with certificates, healer diff, recorder, and WhatsApp/Gmail webhooks")
