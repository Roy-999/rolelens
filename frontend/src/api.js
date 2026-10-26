const API_BASE = "/api";
// Vision extraction can include two bounded provider operations (up to 49 seconds).
// Let Nginx's 60-second upstream timeout return its response before aborting locally.
const REQUEST_TIMEOUT_MS = 65000;

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const hasJsonBody = contentType.includes("application/json");

  if (response.ok) {
    if (response.status === 204) {
      return null;
    }
    if (hasJsonBody) {
      return response.json();
    }
    return response.text();
  }

  let message = "Request failed.";
  try {
    if (hasJsonBody) {
      const payload = await response.json();
      message = payload.detail || payload.message || message;
      if (Array.isArray(message))
        message = message
          .map((item) => `${item.loc?.slice(1).join(".") || "Input"}: ${item.msg}`)
          .join("; ");
    } else {
      message = await response.text();
    }
  } catch {
    message = `Request failed with status ${response.status}.`;
  }

  throw new Error(message || "Request failed.");
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
    return await parseResponse(response);
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Network request failed. Please try again.");
  } finally {
    clearTimeout(timeout);
  }
}

export async function extractCandidate(file) {
  const formData = new FormData();
  formData.append("file", file);

  return request("/candidates/extract", {
    method: "POST",
    body: formData,
  });
}

export async function submitCandidate(payload) {
  return request("/candidates/submit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function updateCandidate(candidateId, payload) {
  return request(`/candidates/${candidateId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function extractJobOrder({ file, jobOrder }) {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  }
  if (jobOrder) {
    formData.append("job_order", jobOrder);
  }

  return request("/job-orders/extract", {
    method: "POST",
    body: formData,
  });
}

export async function submitJobOrder(payload) {
  return request("/job-orders/submit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function updateJobOrder(jobOrderId, payload) {
  return request(`/job-orders/${jobOrderId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function getGmailStatus() {
  return request("/gmail/status");
}

export function getGmailLoginUrl() {
  return `${API_BASE}/gmail/login`;
}

export async function testFetchGmailMessages() {
  return request("/gmail/test-fetch", {
    method: "POST",
  });
}

export async function processLatestGmailMessages() {
  return request("/gmail/process-latest", {
    method: "POST",
  });
}

export async function disconnectGmail() {
  return request("/gmail/disconnect", {
    method: "POST",
  });
}

export async function listEmailJobOrderDrafts({ status } = {}) {
  const params = new URLSearchParams();
  if (status) {
    params.set("status_filter", status);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request(`/gmail/job-order-drafts${suffix}`);
}

export async function getEmailJobOrderDraft(draftId) {
  return request(`/gmail/job-order-drafts/${draftId}`);
}

export async function saveEmailJobOrderDraft(draftId, payload) {
  return request(`/gmail/job-order-drafts/${draftId}/save`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function dismissEmailJobOrderDraft(draftId) {
  return request(`/gmail/job-order-drafts/${draftId}/dismiss`, {
    method: "POST",
  });
}

export async function getJobOrderStats() {
  return request("/job-orders/stats");
}

export async function listJobOrders({ country, state, city, domain } = {}) {
  const params = new URLSearchParams();
  if (country) {
    params.set("country_filter", country);
  }
  if (state) {
    params.set("state_filter", state);
  }
  if (city) {
    params.set("city_filter", city);
  }
  if (domain) {
    params.set("domain_filter", domain);
  }

  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request(`/job-orders${suffix}`);
}

export async function getCandidateStats() {
  return request("/candidates/stats");
}

export async function listCandidates() {
  return request("/candidates");
}

export async function matchJob({ file, jobOrder, limit = 3, city }) {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  }
  if (jobOrder) {
    formData.append("job_order", jobOrder);
  }
  formData.append("limit", String(limit));
  if (city) formData.append("city_filter", city);

  return request("/jobs/match", {
    method: "POST",
    body: formData,
  });
}

export async function extractSalary({ file, jobOrder }) {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  }
  if (jobOrder) {
    formData.append("job_order", jobOrder);
  }

  return request("/jobs/salary", {
    method: "POST",
    body: formData,
  });
}

export async function classifyWeightedActivity(candidateId) {
  return request(`/activity/weighted/${candidateId}`);
}

export function getCapabilities() {
  return request("/capabilities");
}
