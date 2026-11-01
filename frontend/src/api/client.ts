import type { AnalysisDetail, AnalysisList, AnalysisSummary, Health } from "./types";

export const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === "string") return first.msg;
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    throw new ApiError(extractDetail(body, `Request failed (${res.status})`), res.status);
  }
  return body as T;
}

export function health(): Promise<Health> {
  return request<Health>("/health");
}

export interface ListParams {
  page?: number;
  pageSize?: number;
  q?: string;
}

export function listAnalyses({ page = 1, pageSize = 20, q }: ListParams = {}): Promise<AnalysisList> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (q && q.trim()) params.set("q", q.trim());
  return request<AnalysisList>(`/analyses?${params.toString()}`);
}

export function getAnalysis(id: string): Promise<AnalysisDetail> {
  return request<AnalysisDetail>(`/analyses/${encodeURIComponent(id)}`);
}

export function deleteAnalysis(id: string): Promise<void> {
  return request<void>(`/analyses/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function fileUrl(id: string, path: string): string {
  const safePath = path.split("/").map(encodeURIComponent).join("/");
  return `${API_BASE}/analyses/${encodeURIComponent(id)}/files/${safePath}`;
}

/** Uses XMLHttpRequest so upload progress (0..1) can be reported. */
export function uploadAnalysis(
  file: File,
  onProgress?: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<AnalysisSummary> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/analyses`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(1);
        resolve(body as AnalysisSummary);
      } else {
        reject(new ApiError(extractDetail(body, `Upload failed (${xhr.status})`), xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("Upload failed. Could not reach the server.", 0));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", 0));
    if (signal) {
      if (signal.aborted) return xhr.abort();
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
