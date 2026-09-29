/**
 * Dashboard Controller
 * Fetches analytics, spend trends, category distribution, recent RFQs, and initializes Chart.js
 */

document.addEventListener("DOMContentLoaded", async () => {
  if (!api.requireAuth()) return;
  initSidebarUser();

  try {
    await Promise.all([
      loadAnalytics(),
      loadRecentRFQs(),
    ]);
  } catch (err) {
    showToast("Error loading dashboard data: " + err.message, "error");
  }
});

let spendChartInstance = null;
let categoryChartInstance = null;

async function loadAnalytics() {
  try {
    const data = await api.ai.analytics();
    const stats = data.stats || {};

    // Update KPI numbers
    const formatCurrency = (val) => "$" + Number(val || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

    const budgetEl = document.getElementById("kpi-budget");
    if (budgetEl) budgetEl.textContent = formatCurrency(stats.total_budget);

    const savingsEl = document.getElementById("kpi-savings");
    if (savingsEl) savingsEl.textContent = formatCurrency(stats.estimated_savings);

    const rfqsEl = document.getElementById("kpi-rfqs");
    if (rfqsEl) rfqsEl.textContent = stats.total_rfqs || 0;

    const matchEl = document.getElementById("kpi-match-score");
    if (matchEl) matchEl.textContent = (stats.avg_ai_match_score || 90.3).toFixed(1) + "%";

    // Render Charts
    renderSpendChart(data.spend_trends);
    renderCategoryChart(data.categories);

    // Render Top Rated Vendors
    renderTopVendors(data.top_rated_vendors || []);
  } catch (err) {
    console.error("Failed to load analytics:", err);
  }
}

function renderSpendChart(trends) {
  const ctx = document.getElementById("spendTrendChart");
  if (!ctx || !trends) return;

  if (spendChartInstance) spendChartInstance.destroy();

  spendChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: trends.labels || ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"],
      datasets: [
        {
          label: "Allocated Budget ($)",
          data: trends.allocated_budget || [],
          backgroundColor: "rgba(148, 163, 184, 0.4)",
          borderColor: "#94a3b8",
          borderWidth: 1,
          borderRadius: 4,
          order: 2,
        },
        {
          label: "Actual Spend ($)",
          data: trends.actual_spend || [],
          backgroundColor: "rgba(59, 130, 246, 0.8)",
          borderColor: "#2563eb",
          borderWidth: 1,
          borderRadius: 4,
          order: 2,
        },
        {
          type: "line",
          label: "AI-Negotiated Savings ($)",
          data: trends.ai_savings || [],
          borderColor: "#8b5cf6",
          backgroundColor: "rgba(139, 92, 246, 0.15)",
          borderWidth: 3,
          fill: true,
          tension: 0.35,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          position: "top",
          labels: {
            boxWidth: 12,
            font: { family: "Inter", size: 12 },
          },
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              let label = context.dataset.label || "";
              if (label) label += ": ";
              if (context.parsed.y !== null) {
                label += "$" + context.parsed.y.toLocaleString();
              }
              return label;
            },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: "#f1f5f9" },
          ticks: {
            font: { family: "Inter", size: 11 },
            callback: (val) => "$" + (val >= 1000 ? (val / 1000) + "k" : val),
          },
        },
        x: {
          grid: { display: false },
          ticks: { font: { family: "Inter", size: 11 } },
        },
      },
    },
  });
}

function renderCategoryChart(categories) {
  const ctx = document.getElementById("categoryChart");
  if (!ctx || !categories) return;

  if (categoryChartInstance) categoryChartInstance.destroy();

  categoryChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: categories.labels || [],
      datasets: [
        {
          data: categories.counts || [],
          backgroundColor: [
            "#3b82f6",
            "#8b5cf6",
            "#10b981",
            "#f59e0b",
            "#ec4899",
            "#64748b",
          ],
          borderWidth: 2,
          borderColor: "#ffffff",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            boxWidth: 10,
            font: { family: "Inter", size: 11 },
            padding: 12,
          },
        },
      },
      cutout: "68%",
    },
  });
}

async function loadRecentRFQs() {
  const tbody = document.getElementById("recent-rfqs-body");
  if (!tbody) return;

  try {
    const rfqs = await api.rfq.list();
    if (!rfqs || rfqs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">No active RFQs found. Click "New RFQ" to begin.</td></tr>`;
      return;
    }

    tbody.innerHTML = rfqs.slice(0, 5).map(r => {
      const statusBadge = r.status === "Open" ? "bg-success-subtle text-success border border-success-subtle" :
                          r.status === "Awarded" ? "bg-primary-subtle text-primary border border-primary-subtle" :
                          "bg-secondary-subtle text-secondary";
      return `
        <tr>
          <td>
            <div class="fw-semibold text-dark text-truncate" style="max-width: 200px;">${escapeHtml(r.title)}</div>
            <span class="text-muted" style="font-size: 0.72rem;">Due: ${r.deadline || "TBD"}</span>
          </td>
          <td><span class="badge bg-light text-dark border">${escapeHtml(r.category)}</span></td>
          <td class="fw-semibold text-dark">$${Number(r.budget || 0).toLocaleString()}</td>
          <td><span class="badge bg-primary-subtle text-primary">${r.quote_count || 0} quotes</span></td>
          <td><span class="badge ${statusBadge}">${r.status}</span></td>
          <td>
            <a href="/pages/rfq.html?id=${r.id}" class="btn btn-sm btn-outline-primary d-inline-flex align-items-center gap-1">
              <i class="bi bi-stars"></i>
              <span>AI Match</span>
            </a>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger">Failed to load RFQs: ${err.message}</td></tr>`;
  }
}

function renderTopVendors(vendors) {
  const tbody = document.getElementById("top-vendors-body");
  if (!tbody) return;

  if (!vendors || vendors.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" class="text-center py-4 text-muted">No vendors available.</td></tr>`;
    return;
  }

  tbody.innerHTML = vendors.map(v => {
    return `
      <tr>
        <td>
          <div class="fw-semibold text-dark text-truncate" style="max-width: 170px;">${escapeHtml(v.name)}</div>
          <span class="text-muted" style="font-size: 0.72rem;">${escapeHtml(v.category)}</span>
        </td>
        <td><span class="badge bg-light text-secondary border">${escapeHtml(v.pricing || "Standard")}</span></td>
        <td>
          <span class="badge bg-warning-subtle text-dark border border-warning-subtle">
            <i class="bi bi-star-fill text-warning me-1"></i>${Number(v.performance_rating || 4.0).toFixed(2)}
          </span>
        </td>
      </tr>
    `;
  }).join("");
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
