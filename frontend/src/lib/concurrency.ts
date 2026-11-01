/** Runs async tasks with at most `limit` in flight; never rejects (each task handles its own errors). */
export async function runWithConcurrency<T>(
  items: T[],
  limit: number,
  worker: (item: T) => Promise<void>,
): Promise<void> {
  let next = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const item = items[next++];
      try {
        await worker(item);
      } catch {
        // Workers report their own failures; keep the pool draining.
      }
    }
  });
  await Promise.all(runners);
}
