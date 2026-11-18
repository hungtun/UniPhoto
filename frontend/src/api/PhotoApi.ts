import { invoke } from "@tauri-apps/api/core";
import { getInitialLanguage, translations } from "../i18n/translations";

const DEFAULT_API_BASE = "http://127.0.0.1:8000/api/v1";
let cachedApiBase: string | null = null;
let resolvingApiBasePromise: Promise<string> | null = null;

export async function resolveApiBase(): Promise<string> {
  if (cachedApiBase) {
    return cachedApiBase;
  }
  if (!resolvingApiBasePromise) {
    resolvingApiBasePromise = (async () => {
      try {
        const url = await invoke<string>("get_backend_url");
        if (typeof url === "string" && url.trim().length > 0) {
          cachedApiBase = url.trim().replace(/\/+$/, "");
          return cachedApiBase;
        }
      } catch {
        // Fallback when running outside Tauri runtime (e.g. plain browser dev)
      }
      cachedApiBase = DEFAULT_API_BASE;
      return cachedApiBase;
    })();
  }
  return resolvingApiBasePromise;
}

function apiText() {
  return translations[getInitialLanguage()].api;
}

export interface PhotoItem {
  id: number;
  file_name: string;
  folder_name: string;
  file_path: string;
  file_size: number;
  width: number | null;
  height: number | null;
  timestamp: string | null;
  status: "keep" | "exact_duplicate" | "delete";
  is_best: boolean;
  quality_score: number | null;
  sharpness_score: number | null;
  exposure_score: number | null;
  contrast_score: number | null;
  aesthetic_score: number | null;
  composition_score: number | null;
  face_score: number | null;
  tilt_angle: number | null;
  has_closed_eyes: boolean | null;
  aesthetic_tags: string[];
  thumbnail_url: string;
}

export interface ClusterGroup {
  cluster_id: number;
  best_photo_id: number | null;
  photo_count: number;
  has_aesthetic_scores: boolean;
  photos: PhotoItem[];
}

export interface ScanResponse {
  message: string;
  total_found: number;
  new_added: number;
  exact_duplicates: number;
  already_indexed: number;
  duration_seconds: number;
  cancelled?: boolean;
}

export interface ClusterResponse {
  message: string;
  photos_processed: number;
  clusters_created: number;
  duration_seconds: number;
  cancelled?: boolean;
}

export interface AestheticScoreResponse {
  message: string;
  clusters_scored: number;
  photos_scored: number;
  best_changed_count: number;
  duration_seconds: number;
  cancelled?: boolean;
}

export interface DeleteMultipleResponse {
  message: string;
  deleted_count: number;
  freed_bytes: number;
}

export interface ClusterListResponse {
  total_clusters: number;
  total_bytes?: number;
  total_photos?: number;
  disconnected_volumes?: string[];
  items: ClusterGroup[];
}

export interface DuplicateGroup {
  group_index: number;
  phash: string;
  best_photo_id: number | null;
  total_photos: number;
  duplicate_count: number;
  photos: PhotoItem[];
}

export interface DuplicateListResponse {
  total_groups: number;
  total_bytes?: number;
  total_photos?: number;
  disconnected_volumes?: string[];
  items: DuplicateGroup[];
}

export interface ScanProgressState {
  phase:
    | "idle"
    | "scanning"
    | "clustering"
    | "aesthetic_scoring"
    | "cancelled"
    | "done";
  current: number;
  total: number;
  percent: number;
  current_file: string;
  new_added: number;
  exact_duplicates: number;
  already_indexed: number;
  cancel_requested?: boolean;
}

export async function checkBackendHealthApi(): Promise<boolean> {
  const base = await resolveApiBase();
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), 1200);
  try {
    const res = await fetch(`${base}/health`, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    globalThis.clearTimeout(timer);
  }
}

export async function fetchScanProgressApi(): Promise<ScanProgressState> {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/scan/progress`);
  if (!res.ok) throw new Error(apiText().errProgress);
  return res.json();
}

export async function cancelScanApi(): Promise<{
  message: string;
  cancel_requested: boolean;
}> {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/scan/cancel`, {
    method: "POST",
  });
  if (!res.ok) {
    let detail = "";
    try {
      const err = await res.json();
      detail = err.detail || "";
    } catch {
      // Ignore non-JSON error responses
    }
    throw new Error(detail || apiText().errCancelScan);
  }
  return res.json();
}

export async function scanDirectoryApi(
  folderPath: string
): Promise<ScanResponse> {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_path: folderPath }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || apiText().errScan);
  }
  return res.json();
}

export async function clusterPhotosApi(
  similarityThreshold = 0.85
): Promise<ClusterResponse> {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/cluster`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      batch_size: 16,
      similarity_threshold: similarityThreshold,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || apiText().errCluster);
  }
  return res.json();
}

export async function scoreClusterAestheticsApi(): Promise<AestheticScoreResponse> {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/cluster/aesthetic-score`, {
    method: "POST",
  });
  if (!res.ok) {
    let detail = "";
    try {
      const err = await res.json();
      detail = err.detail || "";
    } catch {
      // Ignore non-JSON error responses
    }
    throw new Error(detail || apiText().errAesthetic);
  }
  return res.json();
}

export async function fetchClustersApi(
  limit = 100,
  offset = 0
): Promise<ClusterListResponse> {
  const base = await resolveApiBase();
  const res = await fetch(
    `${base}/photos/clusters?limit=${limit}&offset=${offset}`
  );
  if (!res.ok) throw new Error(apiText().errLoadClusters);
  return res.json();
}

export async function fetchDuplicatesApi(
  limit = 100,
  offset = 0
): Promise<DuplicateListResponse> {
  const base = await resolveApiBase();
  const res = await fetch(
    `${base}/photos/duplicates?limit=${limit}&offset=${offset}`
  );
  if (!res.ok) throw new Error(apiText().errLoadDuplicates);
  return res.json();
}

export async function rescorePhotosApi() {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/photos/rescore`, { method: "POST" });
  if (!res.ok) throw new Error(apiText().errRescore);
  return res.json();
}

export async function openPhotoOnMacApi(
  photoId: number,
  mode: "preview" | "finder" = "preview"
) {
  const base = await resolveApiBase();
  await fetch(`${base}/photos/${photoId}/open?mode=${mode}`, {
    method: "POST",
  });
}

export async function openMultiplePhotosOnMacApi(photoIds: number[]) {
  const base = await resolveApiBase();
  await fetch(`${base}/photos/open-multiple`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
}

export async function deletePhotoApi(photoId: number) {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/photos/${photoId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || apiText().errDeletePhoto);
  }
  return res.json();
}

export async function deleteMultiplePhotosApi(
  photoIds: number[]
): Promise<DeleteMultipleResponse> {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/photos/delete-multiple`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const err = await res.json();
      detail = err.detail || "";
    } catch {
      // Ignore non-JSON error responses
    }
    throw new Error(detail || apiText().errDeleteMultiple);
  }
  return res.json();
}

export async function resetDatabaseApi() {
  const base = await resolveApiBase();
  const res = await fetch(`${base}/photos/reset`, { method: "POST" });
  if (!res.ok) throw new Error(apiText().errResetDb);
  return res.json();
}
