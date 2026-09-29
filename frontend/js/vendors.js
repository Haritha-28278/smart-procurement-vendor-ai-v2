/**
 * Vendors Registry Controller
 * Handles CRUD operations, category filters, search debounce, and detail modals.
 */

let vendorModalInstance = null;
let detailModalInstance = null;
let allVendorsCache = [];

document.addEventListener("DOMContentLoaded", async () => {
  if (!api.requireAuth()) return;
  initSidebarUser();

  const modalEl = document.getElementById("vendorModal");
  if (modalEl) vendorModalInstance = new bootstrap.Modal(modalEl);

  const detailEl = document.getElementById("vendorDetailModal");
  if (detailEl) detailModalInstance = new bootstrap.Modal(detailEl);

  // Load initial data
  await loadCategories();
  await loadVendors();

  // Search input debounce
  const searchInput = document.getElementById("vendorSearchInput");
  if (searchInput) {
    let timeout = null;
    searchInput.addEventListener("input", () => {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        loadVendors();
      }, 300);
    });
  }

  // Category filter
  const categoryFilter = document.getElementById("vendorCategoryFilter");
  if (categoryFilter) {
    categoryFilter.addEventListener("change", () => loadVendors());
  }

  // Form submit
  const vendorForm = document.getElementById("vendorForm");
  if (vendorForm) {
    vendorForm.addEventListener("submit", handleVendorSave);
  }
});

async function loadCategories() {
  try {
    const categories = await api.vendors.categories();
    const select = document.getElementById("vendorCategoryFilter");
    if (!select) return;

    // Preserve "All Categories"
    select.innerHTML = '<option value="All">All Categories</option>';
    categories.forEach(cat => {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to load categories:", err);
  }
}

async function loadVendors() {
  const tbody = document.getElementById("vendorsTableBody");
  const countBadge = document.getElementById("vendorCountBadge");
  const category = document.getElementById("vendorCategoryFilter")?.value || "All";
  const search = document.getElementById("vendorSearchInput")?.value.trim() || "";

  try {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading suppliers...</td></tr>`;

    const vendors = await api.vendors.list(category, search);
    allVendorsCache = vendors;

    if (countBadge) {
      countBadge.textContent = `${vendors.length} registered`;
    }

    if (!vendors || vendors.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted">No suppliers matched your criteria.</td></tr>`;
      return;
    }

    tbody.innerHTML = vendors.map(v => {
      const pricingColor = v.pricing === "Premium" ? "bg-purple-subtle text-purple border" :
                           v.pricing === "Budget" ? "bg-success-subtle text-success border border-success-subtle" :
                           "bg-primary-subtle text-primary border border-primary-subtle";

      const certsList = (v.certifications || "").split(",")
        .filter(c => c.trim())
        .slice(0, 2)
        .map(c => `<span class="badge bg-light text-secondary border me-1">${escapeHtml(c.trim())}</span>`)
        .join("");

      return `
        <tr>
          <td>
            <div class="fw-bold text-dark">${escapeHtml(v.name)}</div>
            <span class="text-muted" style="font-size: 0.75rem;">${escapeHtml(v.contact_email || "No direct email")}</span>
          </td>
          <td><span class="badge bg-light text-dark border">${escapeHtml(v.category)}</span></td>
          <td><span class="badge ${pricingColor}">${escapeHtml(v.pricing)}</span></td>
          <td>
            <span class="badge bg-warning-subtle text-dark border border-warning-subtle">
              <i class="bi bi-star-fill text-warning me-1"></i>${Number(v.performance_rating || 4.0).toFixed(2)}
            </span>
          </td>
          <td class="text-muted small"><i class="bi bi-geo-alt me-1"></i>${escapeHtml(v.location)}</td>
          <td>${certsList || '<span class="text-muted small">None listed</span>'}</td>
          <td class="text-end">
            <div class="btn-group btn-group-sm">
              <button class="btn btn-outline-secondary" onclick="viewVendorDetail(${v.id})" title="View Details">
                <i class="bi bi-eye"></i>
              </button>
              <button class="btn btn-outline-primary" onclick="openEditVendorModal(${v.id})" title="Edit Vendor">
                <i class="bi bi-pencil"></i>
              </button>
              <button class="btn btn-outline-danger" onclick="deleteVendor(${v.id}, '${escapeHtml(v.name)}')" title="Delete">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-danger">Failed to load vendors: ${err.message}</td></tr>`;
  }
}

function resetFilters() {
  const sInput = document.getElementById("vendorSearchInput");
  const cFilter = document.getElementById("vendorCategoryFilter");
  if (sInput) sInput.value = "";
  if (cFilter) cFilter.value = "All";
  loadVendors();
}

function openAddVendorModal() {
  document.getElementById("vendorFormTitle")?.replaceChildren();
  document.getElementById("vendorModalTitle").innerHTML = `<i class="bi bi-building-add text-primary me-2"></i>Register New Supplier`;
  document.getElementById("vendorForm").reset();
  document.getElementById("vendorFormId").value = "";
  document.getElementById("vRating").value = "4.50";
  document.getElementById("vPricing").value = "Moderate";
  vendorModalInstance.show();
}

function openEditVendorModal(id) {
  const v = allVendorsCache.find(x => x.id === id);
  if (!v) return;

  document.getElementById("vendorModalTitle").innerHTML = `<i class="bi bi-pencil-square text-primary me-2"></i>Edit Supplier Details`;
  document.getElementById("vendorFormId").value = v.id;
  document.getElementById("vName").value = v.name || "";
  document.getElementById("vPricing").value = v.pricing || "Moderate";
  document.getElementById("vCategory").value = v.category || "";
  document.getElementById("vLocation").value = v.location || "";
  document.getElementById("vRating").value = v.performance_rating || 4.0;
  document.getElementById("vEmail").value = v.contact_email || "";
  document.getElementById("vPhone").value = v.contact_phone || "";
  document.getElementById("vWebsite").value = v.website || "";
  document.getElementById("vCertifications").value = v.certifications || "";
  document.getElementById("vPastPerformance").value = v.past_performance || "";

  vendorModalInstance.show();
}

async function handleVendorSave(e) {
  e.preventDefault();
  const id = document.getElementById("vendorFormId").value;
  const btn = document.getElementById("saveVendorBtn");

  const payload = {
    name: document.getElementById("vName").value.trim(),
    pricing: document.getElementById("vPricing").value,
    category: document.getElementById("vCategory").value.trim(),
    location: document.getElementById("vLocation").value.trim(),
    performance_rating: parseFloat(document.getElementById("vRating").value) || 4.0,
    contact_email: document.getElementById("vEmail").value.trim() || null,
    contact_phone: document.getElementById("vPhone").value.trim() || null,
    website: document.getElementById("vWebsite").value.trim() || null,
    certifications: document.getElementById("vCertifications").value.trim() || "",
    past_performance: document.getElementById("vPastPerformance").value.trim() || "",
  };

  try {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Saving...`;

    if (id) {
      await api.vendors.update(id, payload);
      showToast("Vendor updated successfully!", "success");
    } else {
      await api.vendors.create(payload);
      showToast("Vendor registered successfully!", "success");
    }

    vendorModalInstance.hide();
    await loadCategories();
    await loadVendors();
  } catch (err) {
    showToast(err.message || "Failed to save vendor.", "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-check-lg"></i><span>Save Vendor</span>`;
  }
}

async function deleteVendor(id, name) {
  if (!confirm(`Are you sure you want to remove supplier "${name}" from registry? All associated quotes will also be removed.`)) {
    return;
  }

  try {
    await api.vendors.delete(id);
    showToast(`Supplier "${name}" deleted.`, "info");
    await loadVendors();
  } catch (err) {
    showToast(err.message || "Failed to delete vendor.", "error");
  }
}

function viewVendorDetail(id) {
  const v = allVendorsCache.find(x => x.id === id);
  if (!v) return;

  document.getElementById("detailVendorName").innerHTML = `<i class="bi bi-building text-primary me-2"></i>${escapeHtml(v.name)}`;

  const certTags = (v.certifications || "None specified").split(",")
    .map(c => `<span class="badge bg-primary-subtle text-primary border border-primary-subtle me-1 mb-1">${escapeHtml(c.trim())}</span>`)
    .join("");

  document.getElementById("vendorDetailContent").innerHTML = `
    <div class="row g-3 mb-4">
      <div class="col-md-4">
        <label class="text-muted small">Category</label>
        <div class="fw-semibold">${escapeHtml(v.category)}</div>
      </div>
      <div class="col-md-4">
        <label class="text-muted small">Pricing Tier</label>
        <div><span class="badge bg-light text-dark border">${escapeHtml(v.pricing)}</span></div>
      </div>
      <div class="col-md-4">
        <label class="text-muted small">SLA Rating</label>
        <div class="fw-bold text-warning"><i class="bi bi-star-fill me-1"></i>${Number(v.performance_rating).toFixed(2)} / 5.0</div>
      </div>
      <div class="col-md-6">
        <label class="text-muted small">Headquarters</label>
        <div><i class="bi bi-geo-alt me-1 text-muted"></i>${escapeHtml(v.location)}</div>
      </div>
      <div class="col-md-6">
        <label class="text-muted small">Contact</label>
        <div>${escapeHtml(v.contact_email || "N/A")} | ${escapeHtml(v.contact_phone || "N/A")}</div>
      </div>
      ${v.website ? `
      <div class="col-12">
        <label class="text-muted small">Website</label>
        <div><a href="${escapeHtml(v.website)}" target="_blank" class="text-decoration-none">${escapeHtml(v.website)} <i class="bi bi-box-arrow-up-right small"></i></a></div>
      </div>` : ""}
    </div>

    <div class="mb-4">
      <label class="fw-bold small text-dark mb-2">Verified Certifications & Compliance</label>
      <div>${certTags}</div>
    </div>

    <div class="mb-3">
      <label class="fw-bold small text-dark mb-2">Historical Performance & Reliability Record</label>
      <div class="p-3 bg-light rounded-3 border text-secondary small" style="line-height: 1.6;">
        ${escapeHtml(v.past_performance || "No performance narrative recorded yet.")}
      </div>
    </div>
  `;

  detailModalInstance.show();
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
