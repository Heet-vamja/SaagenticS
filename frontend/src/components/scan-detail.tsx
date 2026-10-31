"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Clock3 } from "lucide-react";
import { api } from "@/lib/api";
import type { Finding, Scan } from "@/lib/types";
import { EmptyState, ErrorState, LoadingState } from "./states";
import { Status } from "./workspace";

export function ScanDetail({ id }: { id: string }) {
  const [data, setData] = useState<{ scan: Scan; findings: Finding[] } | null>(
    null,
  );
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.all([api.scan(id), api.findings(id)])
      .then(([scan, findings]) => {
        if (active) {
          setData({ scan, findings });
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id, attempt]);
  if (error)
    return (
      <ErrorState message={error} retry={() => setAttempt((n) => n + 1)} />
    );
  if (!data) return <LoadingState />;
  return (
    <>
      <Link
        href="/scans"
        className="mb-6 inline-flex items-center gap-2 text-xs text-muted-foreground"
      >
        <ArrowLeft size={14} />
        All scans
      </Link>
      <div className="mb-7 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Scan details
          </h1>
          <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
            {data.scan.id}
          </p>
        </div>
        <Status value={data.scan.status} />
      </div>
      {data.scan.status === "PENDING" && (
        <div className="mb-6 flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-900">
          <Clock3 size={20} className="mt-1 shrink-0" />
          <p>
            This scan record is pending. The auditing engine is not connected
            yet, so it will remain pending. No website requests have been made.
          </p>
        </div>
      )}
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        {[
          {
            label: "Overall score",
            value:
              data.scan.overall_score === null
                ? "Not scored"
                : `${data.scan.overall_score} / 100`,
          },
          {
            label: "Started",
            value: data.scan.started_at
              ? new Date(data.scan.started_at).toLocaleString()
              : "Not started",
          },
          {
            label: "Completed",
            value: data.scan.completed_at
              ? new Date(data.scan.completed_at).toLocaleString()
              : "Not completed",
          },
        ].map((x) => (
          <div key={x.label} className="rounded-xl border bg-card p-5">
            <p className="text-xs text-muted-foreground">{x.label}</p>
            <p className="mt-3 text-lg font-medium">{x.value}</p>
          </div>
        ))}
      </div>
      <section className="rounded-xl border bg-card">
        <h2 className="border-b px-5 py-4 text-sm font-semibold">Findings</h2>
        {data.findings.length === 0 ? (
          <EmptyState
            title="No findings yet."
            description="Findings will appear here once deterministic checks can run and collect evidence."
          />
        ) : (
          <div className="divide-y">
            {data.findings.map((f) => (
              <article key={f.id} className="p-5">
                <p className="mb-2 text-xs text-muted-foreground">
                  {f.category} · {f.severity}
                </p>
                <h3 className="font-medium">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {f.description}
                </p>
                {f.recommendation && (
                  <p className="mt-3 text-sm">{f.recommendation}</p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
