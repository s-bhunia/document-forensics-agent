import { useCallback, useRef, useState } from "react";
import { uploadAnalysis } from "../api/client";
import type { AnalysisSummary } from "../api/types";
import { errorMessage } from "../components/ErrorAlert";
import { runWithConcurrency } from "../lib/concurrency";
import { validateFiles, type RejectedFile } from "../lib/fileValidation";

export const UPLOAD_CONCURRENCY = 5;

export type UploadState = "ready" | "uploading" | "failed";

export interface UploadItem {
  key: string;
  file: File;
  state: UploadState;
  progress: number;
  error: string | null;
}

const fileKey = (f: File) => `${f.name}:${f.size}:${f.lastModified}`;

export function useUploadQueue() {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [rejected, setRejected] = useState<RejectedFile[]>([]);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const patch = useCallback((key: string, update: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...update } : it)));
  }, []);

  const addFiles = useCallback((files: File[]) => {
    const existing = new Set(itemsRef.current.map((it) => it.key));
    const fresh = files.filter((f) => !existing.has(fileKey(f)));
    const { accepted, rejected: bad } = validateFiles(fresh, itemsRef.current.length);
    setRejected(bad);
    if (accepted.length > 0) {
      setItems((prev) => [
        ...prev,
        ...accepted.map((file) => ({ key: fileKey(file), file, state: "ready" as const, progress: 0, error: null })),
      ]);
    }
  }, []);

  const remove = useCallback((key: string) => {
    setItems((prev) => prev.filter((it) => it.key !== key));
  }, []);

  const clearRejected = useCallback(() => setRejected([]), []);

  /** Uploads one item; on success removes it from the queue and resolves with the created analysis. */
  const uploadOne = useCallback(
    async (item: UploadItem): Promise<AnalysisSummary> => {
      patch(item.key, { state: "uploading", progress: 0, error: null });
      try {
        const created = await uploadAnalysis(item.file, (p) => patch(item.key, { progress: p }));
        setItems((prev) => prev.filter((it) => it.key !== item.key));
        return created;
      } catch (err) {
        patch(item.key, { state: "failed", progress: 0, error: errorMessage(err) });
        throw err;
      }
    },
    [patch],
  );

  /** Uploads the given items with limited concurrency; each success is reported via onCreated. */
  const uploadMany = useCallback(
    (targets: UploadItem[], onCreated: (a: AnalysisSummary) => void) =>
      runWithConcurrency(targets, UPLOAD_CONCURRENCY, async (item) => onCreated(await uploadOne(item))),
    [uploadOne],
  );

  return { items, rejected, addFiles, remove, clearRejected, uploadOne, uploadMany, patch };
}
