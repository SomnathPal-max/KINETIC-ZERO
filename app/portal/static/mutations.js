/**
 * KINETIC-ZERO Chaos Mutator
 * Follows SPEC.txt Section 6.1.
 * Transforms the DOM deterministically based on seed and active mutation type (M1-M6).
 * Critical constraint: leaves internal data-k0-* attributes untouched so oracle tests remain valid.
 */

(function () {
  // Deterministic seeded PRNG (Linear Congruential Generator)
  function createRng(seed) {
    let s = seed % 2147483647;
    if (s <= 0) s += 2147483646;
    return function () {
      s = (s * 16807) % 2147483647;
      return (s - 1) / 2147483646;
    };
  }

  function randomToken(rng, len = 6) {
    const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
    let res = "k0_mut_";
    for (let i = 0; i < len; i++) {
      res += chars[Math.floor(rng() * chars.length)];
    }
    return res;
  }

  // M1: rename_ids
  function applyM1(rng) {
    const elements = document.querySelectorAll("input, button, textarea, form, select, div, label");
    const idMap = new Map();

    elements.forEach(el => {
      // Don't mutate the judge chaos panel itself
      if (el.closest("#judge-chaos-panel")) return;

      if (el.id) {
        const newId = randomToken(rng);
        idMap.set(el.id, newId);
        el.id = newId;
      }
      if (el.name) {
        el.name = randomToken(rng);
      }
      if (el.className && typeof el.className === "string") {
        el.className = randomToken(rng) + " " + randomToken(rng);
      }
    });

    // Fix label 'for' attributes
    document.querySelectorAll("label[for]").forEach(lbl => {
      if (lbl.closest("#judge-chaos-panel")) return;
      const oldFor = lbl.getAttribute("for");
      if (idMap.has(oldFor)) {
        lbl.setAttribute("for", idMap.get(oldFor));
      }
    });
  }

  // M2: relabel
  function applyM2() {
    const synonymMap = [
      ["Review Claim", "Preview Details"],
      ["Submit for Payment", "Confirm & Send"],
      ["Vendor GSTIN", "Supplier Tax ID"],
      ["Vendor Name", "Supplier Legal Name"],
      ["Invoice No.", "Bill Reference"],
      ["Invoice Date", "Billing Date"],
      ["Taxable Value", "Subtotal Assessment"],
      ["Grand Total", "Total Payable Amount"],
      ["Total", "Payable Sum"]
    ];

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    const textNodes = [];
    while ((node = walker.nextNode())) {
      if (node.parentElement && !node.parentElement.closest("#judge-chaos-panel")) {
        textNodes.push(node);
      }
    }

    textNodes.forEach(tNode => {
      let val = tNode.nodeValue;
      synonymMap.forEach(([orig, syn]) => {
        if (val.includes(orig)) {
          val = val.replaceAll(orig, syn);
        }
      });
      tNode.nodeValue = val;
    });

    // Also update button values and inputs placeholder
    document.querySelectorAll("input[placeholder]").forEach(inp => {
      if (inp.placeholder.includes("GSTIN")) inp.placeholder = "e.g. Tax ID";
      if (inp.placeholder.includes("INV")) inp.placeholder = "BILL-REF";
    });
  }

  // M3: reorder
  function applyM3(rng) {
    const grid = document.querySelector(".grid");
    if (grid) {
      const items = Array.from(grid.children);
      // Shuffle children
      for (let i = items.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        grid.appendChild(items[j]);
      }
    }
    // Swap button positions in action bars
    document.querySelectorAll(".actions").forEach(act => {
      if (act.closest("#judge-chaos-panel")) return;
      act.style.flexDirection = "row-reverse";
      const btns = Array.from(act.children);
      btns.reverse().forEach(b => act.appendChild(b));
    });
  }

  // M4: retag
  function applyM4() {
    document.querySelectorAll("button").forEach(btn => {
      if (btn.closest("#judge-chaos-panel")) return;

      const replacement = document.createElement("a");
      replacement.setAttribute("role", "button");
      replacement.setAttribute("tabindex", "0");
      replacement.className = btn.className;
      replacement.innerHTML = btn.innerHTML;
      if (btn.id) replacement.id = btn.id;

      // Copy attributes
      Array.from(btn.attributes).forEach(attr => {
        if (attr.name.startsWith("data-") || attr.name === "name") {
          replacement.setAttribute(attr.name, attr.value);
        }
      });

      // Handle submit or click simulation
      replacement.addEventListener("click", (e) => {
        if (btn.type === "submit" && btn.form) {
          btn.form.submit();
        } else {
          btn.click();
        }
      });

      btn.parentNode.replaceChild(replacement, btn);
    });

    // Wrap inputs in extra nesting containers
    document.querySelectorAll(".form-group input").forEach(inp => {
      const parent = inp.parentNode;
      const wrap1 = document.createElement("div");
      wrap1.className = "k0-nested-wrap-1";
      const wrap2 = document.createElement("div");
      wrap2.className = "k0-nested-wrap-2";
      parent.replaceChild(wrap1, inp);
      wrap1.appendChild(wrap2);
      wrap2.appendChild(inp);
    });
  }

  // M5: decoy
  function applyM5() {
    // Add visually similar decoy next to primary buttons
    const reviewBtn = document.querySelector("#btn_review, [data-k0-action='review']");
    if (reviewBtn && reviewBtn.parentNode) {
      const decoy = document.createElement("button");
      decoy.type = "button";
      decoy.className = reviewBtn.className;
      decoy.innerText = "Cancel Claim";
      decoy.style.opacity = "0.9";
      decoy.onclick = () => alert("Decoy Clicked! Fake cancel executed.");
      reviewBtn.parentNode.insertBefore(decoy, reviewBtn);
    }

    const submitBtn = document.querySelector("#btn_submit_payment, [data-k0-action='submit_payment']");
    if (submitBtn && submitBtn.parentNode) {
      const decoy = document.createElement("button");
      decoy.type = "button";
      decoy.className = submitBtn.className;
      decoy.innerText = "Cancel Claim";
      decoy.style.background = "#dc2626";
      decoy.onclick = () => alert("Decoy Destructive Clicked!");
      submitBtn.parentNode.insertBefore(decoy, submitBtn);
    }
  }

  // Initialize and load mutation config
  async function initChaos() {
    try {
      const res = await fetch("/portal/_k0/config");
      const config = await res.json();
      const type = config.type || "none";
      const seed = config.seed || 42;
      const rng = createRng(seed);

      const badge = document.getElementById("current-mutation-badge");
      if (badge) badge.innerText = type;

      const sel = document.getElementById("judge-mutation-select");
      if (sel) sel.value = type;

      console.log(`[K0 Chaos Mutator] Applying mutation: ${type} (seed=${seed})`);

      if (type === "M1") {
        applyM1(rng);
      } else if (type === "M2") {
        applyM2();
      } else if (type === "M3") {
        applyM3(rng);
      } else if (type === "M4") {
        applyM4();
      } else if (type === "M5") {
        applyM5();
      } else if (type === "M6") {
        // Combo: M1 + M2 + M3 + M5
        applyM1(rng);
        applyM2();
        applyM3(rng);
        applyM5();
      }
    } catch (e) {
      console.warn("[K0 Chaos Mutator] Config load failed", e);
    }
  }

  // Setup judge button listener
  document.addEventListener("DOMContentLoaded", () => {
    initChaos();

    const applyBtn = document.getElementById("judge-apply-mutate");
    if (applyBtn) {
      applyBtn.addEventListener("click", async () => {
        const sel = document.getElementById("judge-mutation-select");
        const chosen = sel.value;
        await fetch("/portal/_k0/mutate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type: chosen, seed: Math.floor(Math.random() * 1000) })
        });
        window.location.reload();
      });
    }
  });
})();
