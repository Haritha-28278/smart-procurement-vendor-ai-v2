/**
 * RFQs & Claude AI Matching Controller
 * Handles RFQ switching, AI evaluations, quotes submission, and negotiation email generation.
 */

let rfqModalInstance = null;
let quoteModalInstance = null;
let negotiationModalInstance = null;

let currentRfq = null;
let currentNegotiationContext = null;
let allVendorsCache = [];

document.addEventListener("DOMContentLoaded", async () => {
  if (!api.requireAuth()) return;
  initSidebarUser();

  // Modals
  const rfqEl = document.getElementById("rfqModal");
  if (rfqEl) rfqModalInstance = new bootstrap.Modal(rfqEl);

  const quoteEl = document.getElementById("quoteModal");
  if (quoteEl) quoteModalInstance = new bootstrap.Modal(quoteEl);

  const negEl = document.getElementById("negotiationModal");
  if (negEl) negotiationModalInstance = new bootstrap.Modal(negEl);

  // Forms
  document.getElementById("createRfqForm")?.addEventListener("submit", handleCreateRfq);
  document.getElementById("submitQuoteForm")?.addEventListener("submit", handleSubmitQuote);

  // Selector
  document.getElementById("rfqSelector")?.addEventListener("change", (e) => {
    if (e.target.value) {
      loadRFQDetails(e.target.value);
    }
  });

  // Load Vendors for quotation dropdown
  loadVendorsList();

  // Load RFQs
  await loadRFQs();

  // Check URL param for pre-selection
  const urlParams = new URLSearchParams(window.location.search);
  const targetId = urlParams.get("id");
  if (targetId) {
    const sel = document.getElementById("rfqSelector");
    if (sel) {
      sel.value = targetId;
      loadRFQDetails(targetId);
    }
  }
});

async function loadVendorsList() {
  try {
    const vendors = await api.vendors.list();
    allVendorsCache = vendors;
    const sel = document.getElementById("quoteVendorSelect");
    if (!sel) return;

    sel.innerHTML = '<option value="">Choose Supplier...</option>' +
      vendors.map(v => `<option value="${v.id}">${escapeHtml(v.name)} (${escapeHtml(v.category)})</option>`).join("");
  } catch (err) {
    console.error("Failed to load vendors list:", err);
  }
}

async function loadRFQs() {
  const sel = document.getElementById("rfqSelector");
  if (!sel) return;

  try {
    const rfqs = await api.rfq.list();
    if (!rfqs || rfqs.length === 0) {
      sel.innerHTML = '<option value="">No RFQs created yet</option>';
      return;
    }

    sel.innerHTML = rfqs.map(r => `
      <option value="${r.id}">${escapeHtml(r.title)} [Budget: $${Number(r.budget || 0).toLocaleString()} - ${r.status}]</option>
    `).join("");

    // Automatically load first RFQ if none selected
    if (rfqs.length > 0 && !sel.value) {
      sel.value = rfqs[0].id;
      loadRFQDetails(rfqs[0].id);
    }
  } catch (err) {
    showToast("Failed to load RFQs: " + err.message, "error");
  }
}

async function loadRFQDetails(rfqId) {
  const card = document.getElementById("rfqDetailCard");
  const tbody = document.getElementById("quotesTableBody");
  const quoteBadge = document.getElementById("quoteCountBadge");

  try {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading RFQ specifications and submissions...</td></tr>`;

    const rfq = await api.rfq.get(rfqId);
    currentRfq = rfq;

    // Populate Details Card
    card.style.display = "block";
    document.getElementById("rfqTitleDisplay").textContent = rfq.title;
    document.getElementById("rfqCategoryBadge").textContent = rfq.category;
    document.getElementById("rfqStatusBadge").textContent = rfq.status;
    document.getElementById("rfqBudgetDisplay").textContent = "$" + Number(rfq.budget || 0).toLocaleString(undefined, { minimumFractionDigits: 2 });
    document.getElementById("rfqDeadlineDisplay").textContent = "Submission Deadline: " + (rfq.deadline || "Open");
    document.getElementById("rfqRequirementsDisplay").textContent = rfq.requirements;

    // Populate Quotes
    const quotes = rfq.quotes || [];
    if (quoteBadge) quoteBadge.textContent = `${quotes.length} quotes submitted`;

    if (quotes.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-5 text-muted">
            <i class="bi bi-inbox fs-3 d-block mb-2 text-secondary"></i>
            No vendor quotes submitted for this RFQ yet.
            <div class="mt-2">
              <button class="btn btn-outline-primary btn-sm" onclick="openSubmitQuoteModal()">
                <i class="bi bi-plus-lg me-1"></i> Submit a Quotation
              </button>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = quotes.map(q => {
      const budget = Number(rfq.budget || 0);
      const quoteAmt = Number(q.quote_amount || 0);
      const variance = quoteAmt - budget;
      const varianceClass = variance <= 0 ? "text-success" : "text-danger";
      const varianceText = variance <= 0 ? `-$${Math.abs(variance).toLocaleString()}` : `+$${variance.toLocaleString()}`;

      // Score Pill
      let scoreHtml = `<span class="badge bg-secondary-subtle text-secondary border">Not Analyzed</span>`;
      if (q.ai_match_score !== null && q.ai_match_score !== undefined) {
        const score = Number(q.ai_match_score);
        const scoreClass = score >= 85 ? "high" : score >= 70 ? "med" : "low";
        scoreHtml = `
          <div class="d-flex align-items-center gap-2">
            <div class="score-pill ${scoreClass}">${score}</div>
            <div>
              <span class="small fw-bold d-block text-dark">${score >= 85 ? 'Strong Match' : score >= 70 ? 'Moderate' : 'Risk'}</span>
              <span class="text-muted" style="font-size: 0.7rem;">Claude 3.5</span>
            </div>
          </div>
        `;
      }

      // Risk Flags & Reasoning
      let flagsHtml = "";
      if (q.ai_risk_flags) {
        try {
          const parsedFlags = typeof q.ai_risk_flags === "string" ? JSON.parse(q.ai_risk_flags) : q.ai_risk_flags;
          if (Array.isArray(parsedFlags)) {
            flagsHtml = parsedFlags.map(f => `<span class="risk-tag"><i class="bi bi-exclamation-triangle"></i> ${escapeHtml(f)}</span>`).join("");
          }
        } catch (e) {
          flagsHtml = `<span class="risk-tag">${escapeHtml(q.ai_risk_flags)}</span>`;
        }
      }

      const reasoningHtml = q.ai_reasoning ?
        `<div class="small text-secondary mb-1" style="line-height: 1.4;">${escapeHtml(q.ai_reasoning)}</div>` :
        `<span class="text-muted small fst-italic">Click "Run Claude Matching" to generate evaluation</span>`;

      // Status Badge
      const statusBadge = q.status === "Accepted" ? "bg-success text-white" :
                          q.status === "Shortlisted" ? "bg-primary text-white" :
                          q.status === "Rejected" ? "bg-danger text-white" : "bg-light text-dark border";

      return `
        <tr>
          <td>
            <div class="fw-bold text-dark">${escapeHtml(q.vendor_name)}</div>
            <div class="small text-muted"><i class="bi bi-star-fill text-warning me-1"></i>${Number(q.vendor_rating || 4.0).toFixed(2)} rating • ${escapeHtml(q.vendor_pricing || "Standard")}</div>
          </td>
          <td>
            <div class="fw-bold text-dark">$${quoteAmt.toLocaleString()}</div>
            <span class="small ${varianceClass} fw-semibold">${varianceText} vs budget</span>
          </td>
          <td>
            <div class="fw-semibold text-dark">${q.delivery_timeline_days} days</div>
            <span class="text-muted small">Delivery SLA</span>
          </td>
          <td>${scoreHtml}</td>
          <td>
            ${reasoningHtml}
            <div>${flagsHtml}</div>
          </td>
          <td><span class="badge ${statusBadge}">${q.status}</span></td>
          <td class="text-end">
            <div class="dropdown">
              <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
                Actions
              </button>
              <ul class="dropdown-menu dropdown-menu-end shadow">
                <li>
                  <button class="dropdown-item d-flex align-items-center gap-2 text-primary" onclick="openNegotiationAssistant(${q.rfq_id}, ${q.vendor_id}, ${q.id}, '${escapeHtml(q.vendor_name)}', ${quoteAmt}, ${budget})">
                    <i class="bi bi-magic"></i> Negotiate with Claude
                  </button>
                </li>
                <li><hr class="dropdown-divider"></li>
                <li>
                  <button class="dropdown-item d-flex align-items-center gap-2" onclick="updateQuoteStatus(${q.id}, 'Shortlisted')">
                    <i class="bi bi-bookmark-check text-primary"></i> Shortlist Vendor
                  </button>
                </li>
                <li>
                  <button class="dropdown-item d-flex align-items-center gap-2" onclick="updateQuoteStatus(${q.id}, 'Accepted')">
                    <i class="bi bi-check-circle text-success"></i> Accept & Award
                  </button>
                </li>
                <li>
                  <button class="dropdown-item d-flex align-items-center gap-2" onclick="updateQuoteStatus(${q.id}, 'Rejected')">
                    <i class="bi bi-x-circle text-danger"></i> Decline Quote
                  </button>
                </li>
              </ul>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-danger">Failed to load RFQ: ${err.message}</td></tr>`;
  }
}

async function triggerClaudeMatching() {
  if (!currentRfq) {
    showToast("Please select an RFQ first.", "warning");
    return;
  }

  const loader = document.getElementById("aiMatchingLoader");
  const tableContainer = document.getElementById("quotesTableContainer");
  const btn = document.getElementById("runAiMatchBtn");

  try {
    btn.disabled = true;
    loader.style.display = "flex";
    tableContainer.style.opacity = "0.3";

    const result = await api.ai.matchAll(currentRfq.id, true);
    showToast(`Claude AI successfully evaluated ${result.evaluated_vendors.length} suppliers!`, "success");

    // Reload RFQ details to refresh the table with newly cached scores
    await loadRFQDetails(currentRfq.id);
  } catch (err) {
    showToast("AI Evaluation failed: " + err.message, "error");
  } finally {
    btn.disabled = false;
    loader.style.display = "none";
    tableContainer.style.opacity = "1";
  }
}

function openNewRFQModal() {
  document.getElementById("createRfqForm").reset();
  // Default deadline 30 days ahead
  const d = new Date();
  d.setDate(d.getDate() + 30);
  document.getElementById("rfqDeadlineInput").value = d.toISOString().split("T")[0];
  rfqModalInstance.show();
}

async function handleCreateRfq(e) {
  e.preventDefault();
  const btn = document.getElementById("saveRfqBtn");

  const payload = {
    title: document.getElementById("rfqTitleInput").value.trim(),
    category: document.getElementById("rfqCategoryInput").value.trim(),
    budget: parseFloat(document.getElementById("rfqBudgetInput").value) || 0,
    deadline: document.getElementById("rfqDeadlineInput").value,
    requirements: document.getElementById("rfqRequirementsInput").value.trim(),
  };

  try {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Publishing...`;
    const created = await api.rfq.create(payload);
    showToast("RFQ published successfully!", "success");
    rfqModalInstance.hide();
    await loadRFQs();
    const sel = document.getElementById("rfqSelector");
    if (sel) {
      sel.value = created.id;
      loadRFQDetails(created.id);
    }
  } catch (err) {
    showToast(err.message || "Failed to create RFQ", "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-check-lg"></i><span>Publish RFQ</span>`;
  }
}

function openSubmitQuoteModal() {
  if (!currentRfq) {
    showToast("Please select an RFQ first.", "warning");
    return;
  }
  document.getElementById("submitQuoteForm").reset();
  quoteModalInstance.show();
}

async function handleSubmitQuote(e) {
  e.preventDefault();
  const btn = document.getElementById("saveQuoteBtn");

  const payload = {
    rfq_id: currentRfq.id,
    vendor_id: parseInt(document.getElementById("quoteVendorSelect").value),
    quote_amount: parseFloat(document.getElementById("quoteAmountInput").value),
    delivery_timeline_days: parseInt(document.getElementById("quoteTimelineInput").value),
    proposal_details: document.getElementById("quoteProposalInput").value.trim(),
  };

  try {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Submitting...`;
    await api.quotes.submit(payload);
    showToast("Quote submitted successfully!", "success");
    quoteModalInstance.hide();
    await loadRFQDetails(currentRfq.id);
  } catch (err) {
    showToast(err.message || "Failed to submit quote.", "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Submit Quote";
  }
}

async function updateQuoteStatus(quoteId, status) {
  try {
    await api.quotes.updateStatus(quoteId, status);
    showToast(`Quote marked as ${status}!`, "success");
    await loadRFQDetails(currentRfq.id);
  } catch (err) {
    showToast("Failed to update status: " + err.message, "error");
  }
}

// --- Negotiation Assistant ---
async function openNegotiationAssistant(rfqId, vendorId, quoteId, vendorName, quoteAmt, budget) {
  currentNegotiationContext = { rfqId, vendorId, quoteId, vendorName, quoteAmt, budget };

  document.getElementById("negVendorName").textContent = vendorName;
  const variance = quoteAmt - budget;
  const varianceText = variance > 0 ? `+$${variance.toLocaleString()}` : `-$${Math.abs(variance).toLocaleString()}`;
  document.getElementById("negVariance").textContent = `$${quoteAmt.toLocaleString()} vs $${budget.toLocaleString()} (${varianceText})`;

  document.getElementById("negSubjectInput").value = "Drafting with Claude...";
  document.getElementById("negEmailBodyInput").value = "Consulting Claude AI procurement negotiation model...";

  negotiationModalInstance.show();
  await regenerateNegotiation();
}

async function regenerateNegotiation() {
  if (!currentNegotiationContext) return;
  const tone = document.querySelector('input[name="negTone"]:checked')?.value || "balanced";

  const subjEl = document.getElementById("negSubjectInput");
  const bodyEl = document.getElementById("negEmailBodyInput");

  try {
    subjEl.value = "Drafting with Claude...";
    bodyEl.value = "Consulting Claude AI procurement negotiation model...";

    const res = await api.ai.negotiate(
      currentNegotiationContext.rfqId,
      currentNegotiationContext.vendorId,
      currentNegotiationContext.quoteId,
      tone
    );

    subjEl.value = res.subject || "";
    bodyEl.value = res.email_body || "";
  } catch (err) {
    showToast("Failed to draft negotiation: " + err.message, "error");
  }
}

function copyNegotiationEmail() {
  const subj = document.getElementById("negSubjectInput").value;
  const body = document.getElementById("negEmailBodyInput").value;
  const fullText = `Subject: ${subj}\n\n${body}`;

  navigator.clipboard.writeText(fullText).then(() => {
    showToast("Negotiation draft copied to clipboard!", "success");
  }).catch(() => {
    showToast("Failed to copy automatically. Please select text manually.", "warning");
  });
}

function navigateToCompare() {
  if (!currentRfq) {
    showToast("Please select an RFQ first.", "warning");
    return;
  }
  window.location.href = `/pages/compare.html?rfq_id=${currentRfq.id}`;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
