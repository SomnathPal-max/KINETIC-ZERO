import re

# 1. Update index.html
with open("app/static/console/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Add Inbound Channels Drawer and Truth Certificate button
control_bar_target = '<div class="control-bar">'

inbound_and_control = '''<!-- Inbound Channels Drawer: WhatsApp & Gmail Webhooks -->
      <div class="inbound-channels-drawer">
        <div class="inbound-header">
          <div class="inbound-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--status-emerald);"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
            Automated Inbound Channels • WhatsApp Business & Accounts Payable Gmail
          </div>
          <span class="chip chip-emerald">2 Inbound Streams Active</span>
        </div>
        <div class="inbound-cards-grid">
          <div class="inbound-card">
            <div class="inbound-card-top">
              <span class="inbound-sender">🟢 WhatsApp Business • Apex Industrial (+91 98201 44821)</span>
              <span class="inbound-time">10:42 AM</span>
            </div>
            <div class="inbound-msg">
              "Namaste sir, attaching invoice INV-DEMO-01 (Rs 71,610.17) for precision parts delivery. Please process."
            </div>
            <button class="btn btn-secondary" onclick="ingestFromWhatsApp()" style="font-size: 11px; padding: 4px 10px; margin-top: 8px;">
              📥 Ingest & Verify from WhatsApp
            </button>
          </div>
          <div class="inbound-card">
            <div class="inbound-card-top">
              <span class="inbound-sender">✉️ Gmail AP • billing@apollo-care.in</span>
              <span class="inbound-time">11:15 AM</span>
            </div>
            <div class="inbound-msg">
              "Urgent Cashless Pre-Auth Request: Patient Priya Sharma (PT-10492), Policy POL-88219. Form attached."
            </div>
            <button class="btn btn-secondary" onclick="ingestFromGmail()" style="font-size: 11px; padding: 4px 10px; margin-top: 8px;">
              📥 Ingest & Verify from Gmail
            </button>
          </div>
        </div>
      </div>

      <!-- Control Bar -->
      <div class="control-bar">'''

html = html.replace(control_bar_target, inbound_and_control, 1)

# Add Truth Certificate button in Control Bar
btn_target = '<button class="btn btn-primary" onclick="runPreflightSuite()">'
cert_btns = '''<button class="btn btn-secondary" onclick="downloadTruthCertificate()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            Truth Certificate (PDF)
          </button>
          <button class="btn btn-primary" onclick="runPreflightSuite()">'''

html = html.replace(btn_target, cert_btns, 1)

# Add Record New Task button in Tab 2
tab2_badge_target = '<span class="chip chip-indigo" id="workflow-steps-badge">12 Steps</span>'
record_btn = '''<div style="display: flex; gap: 8px; align-items: center;">
            <button class="btn btn-secondary" onclick="openRecorderModal()" style="font-size: 11.5px; padding: 4px 10px;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></svg>
              Record New Task
            </button>
            <span class="chip chip-indigo" id="workflow-steps-badge">12 Steps</span>
          </div>'''

html = html.replace(tab2_badge_target, record_btn, 1)

# Add Inspect Healer & Audit Certificate buttons in Tab 3
replay_btn_target = '''<button class="btn btn-primary" id="btn-start-run" onclick="startWorkflowExecution()">'''
healer_btns = '''<button class="btn btn-secondary" onclick="openHealerDiffModal()" style="font-size: 12px;">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            Inspect Healer (DOM Diff)
          </button>
          <button class="btn btn-secondary" onclick="downloadRunCertificate()" style="font-size: 12px;">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            Audit Certificate (PDF)
          </button>
          <button class="btn btn-primary" id="btn-start-run" onclick="startWorkflowExecution()">'''

html = html.replace(replay_btn_target, healer_btns, 1)

# Add MSME Section 43B(h) Badge placeholder in Guard Banner
guard_banner_target = '<span id="ai-overruled-chip" class="chip chip-rose" style="display:none;">AI Proposal Overruled</span>'
msme_badge = '''<span id="ai-overruled-chip" class="chip chip-rose" style="display:none;">AI Proposal Overruled</span>
            <span id="msme-badge-chip" class="chip chip-amber" style="display:none;">Sec 43B(h) MSME Clock Active</span>'''

html = html.replace(guard_banner_target, msme_badge, 1)

# Add Modals before </body>
modals_html = '''
  <!-- Visual DOM Healer Inspector Modal -->
  <div id="healer-diff-modal" class="modal-backdrop">
    <div class="modal-dialog" style="max-width: 760px; border-top: 4px solid #818cf8;">
      <div class="modal-dialog-header">
        <h3 class="modal-dialog-title">⚡ 4-Tier Self-Healing Inspector (DOM Attribute Diff)</h3>
        <button class="btn btn-secondary" onclick="closeModal('healer-diff-modal')" style="padding: 3px 10px; font-size: 11px;">Close</button>
      </div>
      <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 14px;">
        Evaluated under <strong>Chaos Mutation M6 (Extreme Combo)</strong> on Target Portal:
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px;">
        <!-- Left: Broken -->
        <div style="background-color: rgba(244, 63, 94, 0.06); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: var(--radius-md); padding: 12px;">
          <div style="font-size: 11px; font-weight: 700; color: var(--status-rose); text-transform: uppercase; margin-bottom: 6px;">
            Broken Selector (Tier 0 Exact Match)
          </div>
          <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-primary); margin-bottom: 8px;">
            #vendor_gstin
          </div>
          <div style="font-size: 11px; color: var(--status-rose);">
            ❌ 404: Element Not Found (DOM Mutation Broken)
          </div>
        </div>
        <!-- Right: Healed -->
        <div style="background-color: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 12px;">
          <div style="font-size: 11px; font-weight: 700; color: var(--status-emerald); text-transform: uppercase; margin-bottom: 6px;">
            Healed Replacement (Tier 1 Scorer)
          </div>
          <div style="font-family: var(--font-mono); font-size: 11px; color: var(--status-blue); margin-bottom: 8px;">
            input[data-k0-field="vendor_gstin"]
          </div>
          <div style="font-size: 11px; color: var(--status-emerald); font-weight: 600;">
            ✓ Semantic Confidence Score: 0.94 / 1.00 (+0.62 Margin)
          </div>
        </div>
      </div>
      <div style="background-color: var(--bg-canvas); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">
          7-Feature Semantic Scoring Vector Breakdown
        </div>
        <table class="enterprise-table" style="font-size: 11px;">
          <thead>
            <tr><th>Attribute</th><th>Observed Candidate</th><th>Weight</th><th>Match Score</th></tr>
          </thead>
          <tbody>
            <tr><td>Tag Name</td><td><code>&lt;input&gt;</code></td><td>20%</td><td style="color:var(--status-emerald);">1.00</td></tr>
            <tr><td>Semantic Label</td><td>"Vendor GSTIN"</td><td>30%</td><td style="color:var(--status-emerald);">0.95</td></tr>
            <tr><td>Nearby Text</td><td>"Legal Company Name"</td><td>20%</td><td style="color:var(--status-emerald);">0.88</td></tr>
            <tr><td>Grid Bounding Box</td><td>Column 1, Row 1</td><td>15%</td><td style="color:var(--status-emerald);">0.92</td></tr>
            <tr><td>Action Target</td><td>Form Input Binding</td><td>15%</td><td style="color:var(--status-emerald);">0.95</td></tr>
          </tbody>
        </table>
      </div>
      <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">
        💾 Cached to SQLite Episodic Memory: <code>data/k0.db</code> (0 ms & 0 LLM calls on rerun)
      </div>
    </div>
  </div>

  <!-- Interactive Task Recorder Modal -->
  <div id="recorder-modal" class="modal-backdrop">
    <div class="modal-dialog" style="max-width: 640px; border-top: 4px solid var(--brand-primary);">
      <div class="modal-dialog-header">
        <h3 class="modal-dialog-title">🎙️ Show-and-Tell Task Recorder (Zero-Code Workflow Capture)</h3>
        <button class="btn btn-secondary" onclick="closeModal('recorder-modal')" style="padding: 3px 10px; font-size: 11px;">Close</button>
      </div>
      <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 14px;">
        Teach KINETIC-ZERO a new portal task by demonstrating it once. The listener captures user clicks, inputs, and element fingerprints.
      </p>
      <div style="margin-bottom: 14px;">
        <label class="control-label" style="display:block; margin-bottom: 4px;">Task Name:</label>
        <input type="text" id="record-task-name" class="rag-input" value="wf_custom_vendor_settlement" style="width: 100%;">
      </div>
      <div id="recorder-stream-box" style="background-color: var(--bg-canvas); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 12px; max-height: 180px; overflow-y: auto; font-family: var(--font-mono); font-size: 11px; margin-bottom: 16px;">
        <div style="color: var(--text-muted);">[Ready] Click 'Start Recording' to begin capturing DOM interactions on the target portal...</div>
      </div>
      <div class="modal-dialog-footer" style="justify-content: space-between;">
        <button class="btn btn-danger" id="btn-start-record" onclick="simulateStartRecording()">
          <span class="pulse-dot" style="margin-right: 4px;"></span> Start Recording
        </button>
        <button class="btn btn-primary" id="btn-save-record" onclick="simulateSaveRecording()" disabled>
          Generate & Save Skill JSON
        </button>
      </div>
    </div>
  </div>
'''

html = html.replace("</body>", modals_html + "\n</body>", 1)

with open("app/static/console/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("SUCCESS: Updated index.html with Inbound Channels, Certificate buttons, and Modals")
