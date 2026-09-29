/**
 * frontend/src/services/api.ts
 * API client for SatQuery AI — Phase 1 (health, query/parse) + Phase 2 (AOI CRUD).
 */

import {
  QueryParseResult,
  SystemHealth,
  AOIRecord,
  AOICreateRequest,
  SearchResponse,
  ChangeAnalysisResponse,
  ReviewResponse,
  ReviewStatus,
  TimelineResponse,
  HypothesisClassificationRequest,
  HypothesisClassificationResponse,
  AssistantChatResponse,
  ProvenanceRecord,
} from "../types";

export async function fetchHealth(): Promise<SystemHealth> {
  const resp = await fetch("/api/health");
  if (!resp.ok) {
    throw new Error(`Health check failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function parseQuery(query: string, operatorCredentials?: { username: string; password: string }): Promise<QueryParseResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (operatorCredentials) {
    const encoded = btoa(`${operatorCredentials.username}:${operatorCredentials.password}`);
    headers["Authorization"] = `Basic ${encoded}`;
  }

  const resp = await fetch("/api/query/parse", {
    method: "POST",
    headers,
    body: JSON.stringify({ query }),
  });

  if (!resp.ok) {
    const errorData = await resp.json().catch(() => ({}));
    throw new Error(errorData.error || `Query parse failed: HTTP ${resp.status}`);
  }

  return resp.json();
}

// ---------------------------------------------------------------------------
// Phase 2 — AOI API
// ---------------------------------------------------------------------------
function _headers(creds?: { username: string; password: string }, isJson: boolean = true): Record<string, string> {
  const h: Record<string, string> = {};
  if (isJson) {
    h["Content-Type"] = "application/json";
  }
  if (creds?.username && creds?.password) {
    h["Authorization"] = `Basic ${btoa(`${creds.username}:${creds.password}`)}`;
  }
  return h;
}

export async function createAOI(
  payload: AOICreateRequest,
  creds?: { username: string; password: string }
): Promise<AOIRecord> {
  const resp = await fetch("/api/aoi", {
    method: "POST",
    headers: _headers(creds, true),
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || err.suggestion || `AOI creation failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function fetchAOIs(
  creds?: { username: string; password: string }
): Promise<AOIRecord[]> {
  const resp = await fetch("/api/aoi", {
    headers: _headers(creds, false),
  });
  if (!resp.ok) throw new Error(`Failed to fetch AOIs: HTTP ${resp.status}`);
  const data = await resp.json();
  return data.aois as AOIRecord[];
}

export async function fetchAOI(
  id: string,
  creds?: { username: string; password: string }
): Promise<AOIRecord> {
  const resp = await fetch(`/api/aoi/${id}`, {
    headers: _headers(creds, false),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `AOI not found: HTTP ${resp.status}`);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Phase 3 — Ingestion & Scenes API
// ---------------------------------------------------------------------------
export async function triggerIngest(
  payload: {
    aoi_id: string;
    start_date: string;
    end_date: string;
    max_cloud_cover?: number;
    max_scenes?: number;
  },
  creds?: { username: string; password: string }
): Promise<{ job_id: string; status: string; message: string }> {
  const resp = await fetch("/api/ingest", {
    method: "POST",
    headers: _headers(creds, true),
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || err.suggestion || `Ingestion failed to start: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function fetchScenes(
  creds?: { username: string; password: string }
): Promise<{ scenes: any[]; count: number }> {
  const resp = await fetch("/api/scenes", {
    headers: _headers(creds, false),
  });
  if (!resp.ok) throw new Error(`Failed to fetch scenes: HTTP ${resp.status}`);
  return resp.json();
}

export async function fetchScene(
  id: string,
  creds?: { username: string; password: string }
): Promise<any> {
  const resp = await fetch(`/api/scenes/${id}`, {
    headers: _headers(creds, false),
  });
  if (!resp.ok) throw new Error(`Scene not found: HTTP ${resp.status}`);
  return resp.json();
}

export async function fetchJob(
  jobId: string,
  creds?: { username: string; password: string }
): Promise<any> {
  const resp = await fetch(`/api/jobs/${jobId}`, {
    headers: _headers(creds, false),
  });
  if (!resp.ok) throw new Error(`Job not found: HTTP ${resp.status}`);
  return resp.json();
}

export async function cancelJob(
  jobId: string,
  creds?: { username: string; password: string }
): Promise<any> {
  const resp = await fetch(`/api/jobs/${jobId}/cancel`, {
    method: "POST",
    headers: _headers(creds, false),
  });
  if (!resp.ok) throw new Error(`Failed to cancel job: HTTP ${resp.status}`);
  return resp.json();
}

// ---------------------------------------------------------------------------
// Phase 5 — Semantic Search API
// ---------------------------------------------------------------------------
export async function searchSemantic(
  payload: {
    query: string;
    top_k?: number;
    threshold?: number;
    aoi_id?: string;
    date_from?: string;
    date_to?: string;
    max_cloud_cover?: number;
  },
  creds?: { username: string; password: string }
): Promise<SearchResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const resp = await fetch("/api/search/semantic", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Semantic search failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function searchImage(
  file: File,
  creds?: { username: string; password: string }
): Promise<SearchResponse> {
  const headers: Record<string, string> = {};
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const formData = new FormData();
  formData.append("file", file);

  const resp = await fetch("/api/search/image", {
    method: "POST",
    headers,
    body: formData,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Image search failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function searchSimilar(
  tileId: string,
  topK: number = 5,
  creds?: { username: string; password: string }
): Promise<SearchResponse> {
  const headers: Record<string, string> = {};
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const resp = await fetch(`/api/search/similar/${tileId}?top_k=${topK}`, {
    headers,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Similar tile search failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Phase 6 — Change Detection API
// ---------------------------------------------------------------------------
export async function runChangeAnalysis(
  payload: {
    aoi_id?: string;
    before_tile_id: string;
    after_tile_id: string;
    baseline_date?: string;
    comparison_date?: string;
  },
  creds?: { username: string; password: string }
): Promise<ChangeAnalysisResponse> {
  const resp = await fetch("/api/change/analyze", {
    method: "POST",
    headers: _headers(creds, true),
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Change analysis failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function reviewChange(
  changeId: string,
  decision: ReviewStatus,
  notes?: string,
  creds?: { username: string; password: string }
): Promise<ReviewResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const resp = await fetch(`/api/change/changes/${changeId}/review`, {
    method: "POST",
    headers,
    body: JSON.stringify({ decision, notes }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Review submission failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Phase 7 & 8 — Multi-Temporal Timeline & Hypotheses API
// ---------------------------------------------------------------------------
export async function fetchTimeline(
  aoiId: string,
  creds?: { username: string; password: string }
): Promise<TimelineResponse> {
  const headers: Record<string, string> = {};
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const resp = await fetch(`/api/timeline?aoi_id=${aoiId}`, { headers });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Failed to fetch timeline: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function classifyHypothesis(
  payload: HypothesisClassificationRequest,
  creds?: { username: string; password: string }
): Promise<HypothesisClassificationResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const resp = await fetch("/api/timeline/classify-hypothesis", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Hypothesis classification failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Phase 10 & 11 — Assistant, Reports & Audit Lineage API
// ---------------------------------------------------------------------------
export async function askAssistant(
  message: string,
  aoiId?: string,
  history?: Array<{ role: string; content: string }>,
  creds?: { username: string; password: string }
): Promise<AssistantChatResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const resp = await fetch("/api/assistant/chat", {
    method: "POST",
    headers,
    body: JSON.stringify({ message, aoi_id: aoiId, history }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `Assistant request failed: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function downloadReport(
  format: "geojson" | "csv" | "json",
  aoiId?: string,
  creds?: { username: string; password: string }
): Promise<Blob> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const resp = await fetch("/api/report/generate", {
    method: "POST",
    headers,
    body: JSON.stringify({ format, aoi_id: aoiId }),
  });
  if (!resp.ok) {
    throw new Error(`Report generation failed: HTTP ${resp.status}`);
  }
  return resp.blob();
}

export async function fetchProvenance(
  entityId?: string,
  creds?: { username: string; password: string }
): Promise<ProvenanceRecord[]> {
  const headers: Record<string, string> = {};
  if (creds) {
    headers["Authorization"] = _authHeader(creds.username, creds.password);
  }
  const url = entityId ? `/api/provenance/${entityId}` : "/api/provenance";
  const resp = await fetch(url, { headers });
  if (!resp.ok) {
    throw new Error(`Provenance fetch failed: HTTP ${resp.status}`);
  }
  const data = await resp.json();
  return (data.lineage || data.records || []) as ProvenanceRecord[];
}


