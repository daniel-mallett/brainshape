import { useState } from "react";
import { syncStructural, syncSemantic, syncFull, type SyncStats } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

type SyncType = "structural" | "semantic" | "full";

export function SyncStatus() {
  const [loading, setLoading] = useState<SyncType | null>(null);
  const [lastResult, setLastResult] = useState<SyncStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runSync(type: SyncType) {
    setLoading(type);
    setError(null);
    try {
      const fn =
        type === "structural"
          ? syncStructural
          : type === "semantic"
            ? syncSemantic
            : syncFull;
      const result = await fn();
      setLastResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div>
      <Separator />
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-medium text-muted-foreground">Sync</span>
          <div className="flex gap-1">
            {(["structural", "semantic", "full"] as const).map((type) => (
              <Button
                key={type}
                variant="secondary"
                size="sm"
                onClick={() => runSync(type)}
                disabled={loading !== null}
                className="h-6 text-xs px-2"
              >
                {loading === type ? "..." : type}
              </Button>
            ))}
          </div>
        </div>
        {error && <p className="text-xs text-destructive">{error}</p>}
        {lastResult && !error && (
          <p className="text-xs text-muted-foreground">
            {JSON.stringify(lastResult.stats)}
          </p>
        )}
      </div>
    </div>
  );
}
