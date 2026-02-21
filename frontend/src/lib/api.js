const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export function fetchStrains(q = "", type = "", limit = 50) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (type) params.set("type", type);
  if (limit) params.set("limit", String(limit));
  return request(`/strains?${params}`);
}

export function fetchStrain(name) {
  return request(`/strains/${encodeURIComponent(name)}`);
}

export function fetchExplanation(name) {
  return request(`/strains/${encodeURIComponent(name)}/explain`);
}

export function matchEffects(effects, type = "", limit = 20, explain = false) {
  return request("/match", {
    method: "POST",
    body: JSON.stringify({ effects, type: type || undefined, limit, explain }),
  });
}

export function fetchGraph() {
  return request("/graph");
}

export function fetchGraphNode(nodeId) {
  return request(`/graph/${encodeURIComponent(nodeId)}`);
}

export function fetchStats() {
  return request("/stats");
}

export function fetchEffects() {
  return request("/effects");
}

export function predictEffects(profile) {
  return request("/predict", {
    method: "POST",
    body: JSON.stringify(profile),
  });
}
