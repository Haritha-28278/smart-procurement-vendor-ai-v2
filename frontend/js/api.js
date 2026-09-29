/**
 * Smart Procurement Vendor AI - Central API Client & Modular Fetch Wrapper
 * Handles JWT tokens, authentication headers, error handling, and notifications.
 */

const API_BASE = window.location.origin;

class ApiClient {
  constructor() {
    this.tokenKey = "smart_procure_jwt_token";
    this.userKey = "smart_procure_user";
  }

  getToken() {
    return localStorage.getItem(this.tokenKey);
  }

  setToken(token) {
    localStorage.setItem(this.tokenKey, token);
  }

  getUser() {
    const raw = localStorage.getItem(this.userKey);
    return raw ? JSON.parse(raw) : null;
  }

  setUser(user) {
    localStorage.setItem(this.userKey, JSON.stringify(user));
  }

  clearAuth() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
  }

  isAuthenticated() {
    return !!this.getToken();
  }

  requireAuth() {
    if (!this.isAuthenticated()) {
      window.location.href = "/pages/login.html";
      return false;
    }
    return true;
  }

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        // Unauthorized - session expired
        this.clearAuth();
        if (!window.location.pathname.includes("login.html")) {
          window.location.href = "/pages/login.html?session=expired";
        }
        throw new Error("Session expired. Please log in again.");
      }

      if (response.status === 204) {
        return null;
      }

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const errorMsg = data.detail || data.message || `Request failed with status ${response.status}`;
        throw new Error(errorMsg);
      }

      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
  }

  // --- Auth Endpoints ---
  auth = {
    login: async (email, password) => {
      const data = await this.request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      this.setToken(data.access_token);
      this.setUser(data.user);
      return data;
    },
    register: async (email, password, full_name, role) => {
      const data = await this.request("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name, role }),
      });
      this.setToken(data.access_token);
      this.setUser(data.user);
      return data;
    },
    getMe: async () => {
      const user = await this.request("/api/auth/me");
      this.setUser(user);
      return user;
    },
    logout: () => {
      this.clearAuth();
      window.location.href = "/pages/login.html";
    },
  };

  // --- Vendors Endpoints ---
  vendors = {
    list: async (category = "", search = "") => {
      let q = [];
      if (category && category !== "All") q.push(`category=${encodeURIComponent(category)}`);
      if (search) q.push(`search=${encodeURIComponent(search)}`);
      const qs = q.length ? `?${q.join("&")}` : "";
      return await this.request(`/api/vendors${qs}`);
    },
    categories: async () => {
      return await this.request("/api/vendors/categories");
    },
    get: async (id) => {
      return await this.request(`/api/vendors/${id}`);
    },
    create: async (vendorData) => {
      return await this.request("/api/vendors", {
        method: "POST",
        body: JSON.stringify(vendorData),
      });
    },
    update: async (id, vendorData) => {
      return await this.request(`/api/vendors/${id}`, {
        method: "PUT",
        body: JSON.stringify(vendorData),
      });
    },
    delete: async (id) => {
      return await this.request(`/api/vendors/${id}`, {
        method: "DELETE",
      });
    },
  };

  // --- RFQ Endpoints ---
  rfq = {
    list: async (category = "", status = "") => {
      let q = [];
      if (category && category !== "All") q.push(`category=${encodeURIComponent(category)}`);
      if (status && status !== "All") q.push(`status_filter=${encodeURIComponent(status)}`);
      const qs = q.length ? `?${q.join("&")}` : "";
      return await this.request(`/api/rfq${qs}`);
    },
    get: async (id) => {
      return await this.request(`/api/rfq/${id}`);
    },
    create: async (rfqData) => {
      return await this.request("/api/rfq", {
        method: "POST",
        body: JSON.stringify(rfqData),
      });
    },
    update: async (id, rfqData) => {
      return await this.request(`/api/rfq/${id}`, {
        method: "PUT",
        body: JSON.stringify(rfqData),
      });
    },
    delete: async (id) => {
      return await this.request(`/api/rfq/${id}`, {
        method: "DELETE",
      });
    },
  };

  // --- Quotes Endpoints ---
  quotes = {
    list: async (rfqId = null, vendorId = null) => {
      let q = [];
      if (rfqId) q.push(`rfq_id=${rfqId}`);
      if (vendorId) q.push(`vendor_id=${vendorId}`);
      const qs = q.length ? `?${q.join("&")}` : "";
      return await this.request(`/api/quotes${qs}`);
    },
    submit: async (quoteData) => {
      return await this.request("/api/quotes", {
        method: "POST",
        body: JSON.stringify(quoteData),
      });
    },
    updateStatus: async (quoteId, newStatus) => {
      return await this.request(`/api/quotes/${quoteId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
    },
    delete: async (quoteId) => {
      return await this.request(`/api/quotes/${quoteId}`, {
        method: "DELETE",
      });
    },
  };

  // --- Claude AI Analysis Endpoints ---
  ai = {
    matchSingle: async (rfqId, vendorId, forceRefresh = false) => {
      return await this.request(`/api/ai/match/${rfqId}/vendor/${vendorId}?force_refresh=${forceRefresh}`, {
        method: "POST",
      });
    },
    matchAll: async (rfqId, forceRefresh = false) => {
      return await this.request(`/api/ai/match/${rfqId}?force_refresh=${forceRefresh}`, {
        method: "POST",
      });
    },
    compare: async (rfqId, vendorIds = null) => {
      let qs = "";
      if (vendorIds && vendorIds.length) {
        qs = `?vendor_ids=${vendorIds.join(",")}`;
      }
      return await this.request(`/api/ai/compare/${rfqId}${qs}`);
    },
    negotiate: async (rfqId, vendorId, quoteId = null, strategy = "balanced") => {
      return await this.request("/api/ai/negotiate", {
        method: "POST",
        body: JSON.stringify({
          rfq_id: rfqId,
          vendor_id: vendorId,
          quote_id: quoteId,
          strategy: strategy,
        }),
      });
    },
    analytics: async () => {
      return await this.request("/api/ai/analytics");
    },
  };
}

// Global API instance
const api = new ApiClient();

// UI Toast Notification Helper
function showToast(message, type = "info") {
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.className = "toast-container position-fixed bottom-0 end-0 p-3";
    toastContainer.style.zIndex = "1100";
    document.body.appendChild(toastContainer);
  }

  const toastId = "toast-" + Math.random().toString(36).substring(2, 9);
  const bgClass = type === "success" ? "bg-success text-white" :
                  type === "error" || type === "danger" ? "bg-danger text-white" :
                  type === "warning" ? "bg-warning text-dark" : "bg-dark text-white";

  const toastHtml = `
    <div id="${toastId}" class="toast align-items-center ${bgClass} border-0 shadow" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="bi ${type === 'success' ? 'bi-check-circle-fill' : type === 'error' ? 'bi-exclamation-triangle-fill' : 'bi-info-circle-fill'}"></i>
          <span>${message}</span>
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;
  toastContainer.insertAdjacentHTML("beforeend", toastHtml);
  const el = document.getElementById(toastId);
  const bsToast = new bootstrap.Toast(el, { delay: 4000 });
  bsToast.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

// Global Sidebar User Loader
function initSidebarUser() {
  const user = api.getUser();
  if (user) {
    const nameEl = document.getElementById("sidebar-user-name");
    const roleEl = document.getElementById("sidebar-user-role");
    const avatarEl = document.getElementById("sidebar-user-avatar");
    if (nameEl) nameEl.textContent = user.full_name || user.email;
    if (roleEl) roleEl.textContent = user.role || "Member";
    if (avatarEl) {
      const initials = (user.full_name || user.email).substring(0, 2).toUpperCase();
      avatarEl.textContent = initials;
    }
  }
}
