import { useCallback, useState } from "react";

export const BATCH_STORAGE_KEY = "doxket-batch";

function readIds(): string[] {
  try {
    const raw = window.sessionStorage.getItem(BATCH_STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function writeIds(ids: string[]): void {
  try {
    if (ids.length === 0) window.sessionStorage.removeItem(BATCH_STORAGE_KEY);
    else window.sessionStorage.setItem(BATCH_STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // sessionStorage unavailable; the batch just won't survive navigation.
  }
}

/** Analysis ids from the current multi-file batch, persisted for the browser tab's session. */
export function useBatch() {
  const [ids, setIds] = useState<string[]>(readIds);

  const add = useCallback((id: string) => {
    setIds((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      writeIds(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    writeIds([]);
    setIds([]);
  }, []);

  return { ids, add, clear };
}
