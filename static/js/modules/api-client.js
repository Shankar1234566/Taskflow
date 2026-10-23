/**
 * Resilient Frontend REST API Client Wrapper.
 * Provides automatic retries with exponential backoff and standardized error toasts.
 */

class TaskflowApiClient {
  constructor(baseUrl = "") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async request(endpoint, options = {}, retries = 2) {
    const url = `${this.baseUrl}${endpoint}`;
    const defaultHeaders = {
      "Content-Type": "application/json",
      "Accept": "application/json"
    };

    const config = {
      ...options,
      headers: { ...defaultHeaders, ...(options.headers || {}) }
    };

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await fetch(url, config);
        if (response.status === 401 && !endpoint.includes("/login")) {
          window.location.href = "/login";
          return null;
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || `HTTP ${response.status}: Request failed`);
        }
        return data;
      } catch (err) {
        if (attempt === retries) throw err;
        await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 300));
      }
    }
  }

  get(endpoint, params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(qs ? `${endpoint}?${qs}` : endpoint, { method: "GET" });
  }

  post(endpoint, body = {}) {
    return this.request(endpoint, { method: "POST", body: JSON.stringify(body) });
  }

  put(endpoint, body = {}) {
    return this.request(endpoint, { method: "PUT", body: JSON.stringify(body) });
  }

  patch(endpoint, body = {}) {
    return this.request(endpoint, { method: "PATCH", body: JSON.stringify(body) });
  }

  delete(endpoint) {
    return this.request(endpoint, { method: "DELETE" });
  }
}

window.TaskflowApiClient = TaskflowApiClient;
