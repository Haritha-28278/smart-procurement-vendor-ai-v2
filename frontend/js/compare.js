/**
 * Side-by-Side Comparison Controller
 * Fetches multi-vendor analysis and Claude-generated comparative executive summaries.
 */

let currentRfqId = null;

document.addEventListener("DOMContentLoaded", async () => {
  if (!api.requireAuth()) return;
  initSidebarUser();

  const rfqSelect = document.getElementById("compareRfqSelect");
  if (rfqSelect) {
    rfqSelect.addEventListener("change", (e) => {
      if (e.target.value) {
        currentRfqId = e.target.value;
        loadComparison(e.target.value);
      }
    });
  }

  await loadRFQs();

  const urlParams = new URLSearchParams(window.location.search);
  const paramId = urlParams.get("rfq_id");
  if (paramId) {
    currentRfqId = paramId;
    if (rfqSelect) rfqSelect.value = paramId;
    loadComparison(paramId);
  }
});

async function loadRFQs() {
  const sel = document.getElementById("compareRfqSelect");
  if (!sel) return;

  try {
    const rfqs = await api.rfq.list();
    if (!rfqs || rfqs.length === 0) {
      sel.innerHTML = '<option value="">No active RFQs available</option>';
      return;
    }

    sel.innerHTML = rfqs.map(r => `
      <option value="${r.id}">${escapeHtml(r.title)} (Budget: $${Number(r.budget || 0).toLocaleString()})</option>
    `).join("");

    if (!currentRfqId && rfqs.length > 0) {
      currentRfqId = rfqs[0].id;
      sel.value = rfqs[0].id;
      loadComparison(rfqs[0].id);
    }
  } catch (err) {
    showToast("Failed to load RFQs: " + err.message, "error");
  }
}

async function reloadComparison() {
  if (currentRfqId) {
    await loadComparison(currentRfqId);
    showToast("Claude comparison refreshed!", "success");
  }
}

async function loadComparison(rfqId) {
  const loader = document.getElementById("compareLoader");
  const summaryCard = document.getElementById("executiveSummaryCard");
  const grid = document.getElementById("comparisonGrid");
  const container = document.getElementById("comparisonContainer");

  try {
    loader.style.display = "flex";
    container.style.opacity = "0.2";
    summaryCard.style.display = "none";

    const data = await api.ai.compare(rfqId);

    // Populate Claude Executive Summary
    summaryCard.style.display = "block";
    document.getElementById("summaryText").textContent = data.executive_summary || "Comparison generated.";
    document.getElementById("recommendationReason").textContent = data.recommendation_reason || "Based on score and price fit.";

    // Render 3 Vendor Columns
    const vendors = data.vendors || [];
    const recommendedId = data.recommended_vendor_id;
    const targetBudget = Number(data.rfq?.budget || 0);

    if (vendors.length === 0) {
      grid.innerHTML = `
        <div class="col-12 text-center py-5 text-muted">
          <i class="bi bi-inbox fs-2 d-block mb-2"></i>
          No qualified vendor submissions found to compare for this RFQ.
        </div>
      `;
      return;
    }

    grid.innerHTML = vendors.map(item => {
      const v = item.vendor || {};
      const q = item.quote || {};
      const a = item.analysis || {};
      const isWinner = v.id === recommendedId;

      const quoteAmt = Number(q.quote_amount || 0);
      const variance = quoteAmt > 0 ? (quoteAmt - targetBudget) : 0;
      const variancePct = targetBudget > 0 ? ((variance / targetBudget) * 100) : 0;
      const varianceClass = variance <= 0 ? "text-success" : "text-danger";
      const varianceText = quoteAmt > 0 ?
        (variance <= 0 ? `-$${Math.abs(variance).toLocaleString()} (${Math.abs(variancePct).toFixed(1)}% savings)` :
                         `+$${variance.toLocaleString()} (+${variancePct.toFixed(1)}% above budget)`) :
        "No quote submitted";

      const score = Number(a.match_score || 70);
      const scoreColor = score >= 85 ? "#10b981" : score >= 70 ? "#f59e0b" : "#ef4444";

      // Match item in comparison matrix
      const matrixItem = (data.comparison_matrix || []).find(m => m.vendor_id === v.id) || {};

      const certsList = (v.certifications || "").split(",")
        .filter(c => c.trim())
        .map(c => `<span class="badge bg-light text-secondary border me-1 mb-1">${escapeHtml(c.trim())}</span>`)
        .join("") || '<span class="text-muted small">Standard compliance</span>';

      const riskList = (a.risk_flags || [])
        .map(rf => `<span class="risk-tag d-block my-1"><i class="bi bi-exclamation-triangle"></i> ${escapeHtml(rf)}</span>`)
        .join("") || '<span class="text-success small"><i class="bi bi-check-circle me-1"></i>No high-risk flags identified</span>';

      return `
        <div class="col-md-4">
          <div class="compare-header-card h-100 ${isWinner ? 'winner' : ''}">
            ${isWinner ? '<div class="winner-crown"><i class="bi bi-trophy-fill me-1"></i> Claude Optimal Pick</div>' : ''}

            <!-- Vendor Header -->
            <div class="mb-3 pt-2">
              <h5 class="fw-bold text-dark mb-1 text-truncate">${escapeHtml(v.name)}</h5>
              <div class="d-flex align-items-center justify-content-center gap-2">
                <span class="badge bg-light text-dark border">${escapeHtml(v.category)}</span>
                <span class="badge bg-purple-subtle text-purple border">${escapeHtml(v.pricing)} Tier</span>
              </div>
            </div>

            <!-- Score Visual -->
            <div class="p-3 bg-light rounded-3 mb-3 border">
              <div class="d-flex align-items-center justify-content-between mb-1">
                <span class="small fw-semibold text-muted">Claude Match Fit</span>
                <span class="fw-bold" style="color: ${scoreColor}; font-size: 1.1rem;">${score} / 100</span>
              </div>
              <div class="progress" style="height: 8px;">
                <div class="progress-bar" role="progressbar" style="width: ${score}%; background-color: ${scoreColor};"></div>
              </div>
            </div>

            <!-- Commercial Terms -->
            <div class="text-start mb-3 border-bottom pb-3">
              <div class="d-flex justify-content-between align-items-baseline mb-1">
                <span class="text-muted small">Quote Amount:</span>
                <span class="fw-bold fs-5 text-dark">${quoteAmt > 0 ? '$' + quoteAmt.toLocaleString() : 'N/A'}</span>
              </div>
              <div class="d-flex justify-content-between align-items-baseline mb-1">
                <span class="text-muted small">Budget Variance:</span>
                <span class="small fw-bold ${varianceClass}">${varianceText}</span>
              </div>
              <div class="d-flex justify-content-between align-items-baseline">
                <span class="text-muted small">Delivery Timeline:</span>
                <span class="fw-semibold text-dark">${q.delivery_timeline_days ? q.delivery_timeline_days + ' days' : 'Flexible'}</span>
              </div>
            </div>

            <!-- SLA & Location -->
            <div class="text-start mb-3 border-bottom pb-3">
              <div class="d-flex justify-content-between align-items-baseline mb-1">
                <span class="text-muted small">Performance SLA:</span>
                <span class="fw-bold text-warning"><i class="bi bi-star-fill me-1"></i>${Number(v.performance_rating || 4.0).toFixed(2)} / 5.0</span>
              </div>
              <div class="d-flex justify-content-between align-items-baseline">
                <span class="text-muted small">Headquarters:</span>
                <span class="small text-secondary text-truncate" style="max-width: 150px;">${escapeHtml(v.location)}</span>
              </div>
            </div>

            <!-- Key Strengths -->
            <div class="text-start mb-3 border-bottom pb-3">
              <label class="small fw-bold text-muted text-uppercase mb-1"><i class="bi bi-shield-check text-success me-1"></i>Key Strength</label>
              <div class="small text-secondary">${escapeHtml(matrixItem.key_strength || 'Strong historical delivery metrics')}</div>
            </div>

            <!-- Certifications -->
            <div class="text-start mb-3 border-bottom pb-3">
              <label class="small fw-bold text-muted text-uppercase mb-1">Certifications</label>
              <div>${certsList}</div>
            </div>

            <!-- Risk Flags -->
            <div class="text-start mb-4">
              <label class="small fw-bold text-muted text-uppercase mb-1"><i class="bi bi-shield-exclamation text-danger me-1"></i>Risk Assessment</label>
              <div>${riskList}</div>
            </div>

            <!-- Actions -->
            <div class="d-grid gap-2">
              <a href="/pages/rfq.html?id=${rfqId}" class="btn ${isWinner ? 'btn-primary' : 'btn-outline-primary'} btn-sm py-2">
                <i class="bi bi-award me-1"></i> Manage in RFQ Workspace
              </a>
            </div>

          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    grid.innerHTML = `<div class="col-12 text-center py-5 text-danger">Comparison failed: ${err.message}</div>`;
  } finally {
    loader.style.display = "none";
    container.style.opacity = "1";
  }
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
