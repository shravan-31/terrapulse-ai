/**
 * frontend/src/types/index.ts
 * Canonical domain types for SatQuery AI.
 * Aligns with backend models (ADR-007, ADR-012, ADR-013).
 */

export type ChangeType =
  | "construction"
  | "clearance"
  | "water_variation"
  | "vegetation_land_cover"
  | "road_development"
  | "unknown";

export type ChangeKind =
  | "appearance"
  | "disappearance"
  | "expansion"
  | "contraction"
  | "unknown";

export type TemporalStatus =
  | "candidate"
  | "confirmed"
  | "inconsistent"
  | "insufficient_evidence";

export type ReviewStatus =
  | "pending"
  | "confirmed_by_analyst"
  | "rejected_by_analyst"
  | "flagged";

export interface ParsedFilters {
  semantic_prompt: string;
  start_date: string | null;
  end_date: string | null;
  max_cloud_cover: number;
  change_type: ChangeType | null;
  change_kind: ChangeKind | null;
  location_keyword: string | null;
}

export interface QueryParseResult {
  query: string;
  parsed: ParsedFilters;
  used_fallback: boolean;
  parser_model: string;
  notice?: string;
}

export interface SystemHealth {
  status: "ok" | "degraded" | "unavailable";
  app_env: "development" | "production";
  data_mode: "online" | "test";
  dependencies: {
    database: "ok" | "unavailable";
    redis: "ok" | "unavailable";
  };
  compute?: {
    device: string;
    gpu_count?: number;
    gpu_name?: string;
  };
  features: {
    groq: boolean;
    copernicus: boolean;
  };
}

export interface ChangeRecord {
  id: string;
  analysis_id: string;
  change_type: ChangeType;
  change_kind: ChangeKind;
  temporal_status: TemporalStatus;
  last_baseline_observation_at: string | null;
  earliest_supported_at: string;
  confirmed_at: string | null;
  latest_observation_at: string;
  polygon: GeoJSON.Polygon | Record<string, any>;
  area_m2: number;
  pixel_count: number;
  confidence_score: number;
  confidence_details: {
    calibrated: boolean;
    complete_evidence: boolean;
    missing_factors?: string[];
    rejection_reasons?: string[];
  };
  created_at: string;
}

// ---------------------------------------------------------------------------
// Phase 2 — AOI types
// ---------------------------------------------------------------------------
export interface AOIRecord {
  id: string;
  name: string;
  description?: string | null;
  geometry: GeoJSON.Polygon;
  area_km2: number;
  vertex_count: number;
  created_at: string;
  updated_at: string;
  warnings?: string[];
}

export interface AOICreateRequest {
  name: string;
  description?: string;
  geometry: GeoJSON.Polygon;
}

/** Drawing mode for the AOI tool. */
export type AOIDrawMode = "rectangle" | "polygon" | "none";

/** State for the map store (Zustand). */
export interface MapState {
  aoiList: AOIRecord[];
  activeAOI: AOIRecord | null;
  drawMode: AOIDrawMode;
  mapLoaded: boolean;
}

// ---------------------------------------------------------------------------
// Phase 3 — Ingest, Jobs & Scenes types
// ---------------------------------------------------------------------------
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface JobRecord {
  id: string;
  job_type: string;
  status: JobStatus;
  progress_percent: number;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobEvent {
  id: string;
  job_id: string;
  event_type: string;
  message: string;
  event_data: Record<string, any>;
  created_at: string;
}

export interface SceneRecord {
  id: string;
  product_id: string;
  provider: string;
  acquisition_at: string;
  cloud_coverage_percent: number;
  footprint: GeoJSON.Polygon | Record<string, any>;
  crs: string;
  metadata_json: Record<string, any>;
  tile_count?: number;
  created_at: string;
}

export interface IngestRequestPayload {
  aoi_id: string;
  start_date: string;
  end_date: string;
  max_cloud_cover?: number;
  max_scenes?: number;
}

// ---------------------------------------------------------------------------
// Phase 5 — Search types
// ---------------------------------------------------------------------------
export interface SearchResultItem {
  tile_id: string;
  scene_id: string;
  similarity_score: number;
  preview_url?: string;
  metadata?: {
    acquisition_date?: string;
    cloud_cover?: number;
    sensor?: string;
    bbox?: [number, number, number, number];
  };
}

export interface SearchResponse {
  query?: string;
  query_type?: string;
  source_tile_id?: string;
  total_matches: number;
  results: SearchResultItem[];
}

// ---------------------------------------------------------------------------
// Phase 6 — Change Detection types
// ---------------------------------------------------------------------------
export interface ChangeFeature {
  id: string;
  analysis_id?: string;
  change_type: ChangeType;
  change_kind: ChangeKind;
  temporal_status: TemporalStatus;
  area_m2: number;
  pixel_count: number;
  confidence_score: number;
  polygon: GeoJSON.Polygon | Record<string, any>;
  review_status?: ReviewStatus;
}

export interface ChangeAnalysisResponse {
  analysis_id: string;
  status: string;
  duration_ms: number;
  total_changes: number;
  changes: ChangeFeature[];
}

export interface ReviewResponse {
  change_id: string;
  decision: ReviewStatus;
  analyst: string;
  reviewed_at: string;
}

// ---------------------------------------------------------------------------
// Phase 7 & 8 — Timeline & Hypotheses types
// ---------------------------------------------------------------------------
export interface TimelineAcquisition {
  date: string;
  scene_id: string;
  cloud_cover: number;
  changes: ChangeFeature[];
}

export interface TimelineResponse {
  aoi_id: string;
  total_acquisitions: number;
  timeline: TimelineAcquisition[];
}

export interface HypothesisClassificationRequest {
  ndvi_before: number;
  ndvi_after: number;
  ndbi_before: number;
  ndbi_after: number;
  ndwi_before: number;
  ndwi_after: number;
  area_m2: number;
  elongation: number;
}

export interface HypothesisClassificationResponse {
  hypothesis_type: string;
  confidence: number;
  reasoning: string;
  metrics_analyzed: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Phase 10 & 11 — Assistant, Reports & Provenance types
// ---------------------------------------------------------------------------
export interface AssistantCitation {
  entity_type: string;
  entity_id: string;
  confidence?: number;
  snippet?: string;
}

export interface AssistantChatResponse {
  reply: string;
  citations: AssistantCitation[];
  bounded_by_database: boolean;
}

export interface ProvenanceRecord {
  id?: string;
  entity_id: string;
  action: string;
  agent_id: string;
  details_json: Record<string, any>;
  recorded_at: string;
}

