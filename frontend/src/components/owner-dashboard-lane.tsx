"use client";
import { useState } from "react";
import {
  Check,
  CircleAlert,
  LoaderCircle,
  Plus,
  Rocket,
  ShieldCheck,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { DashboardSite, DashboardVariant, SiteJob } from "@/lib/types";
import { Button } from "./ui/button";
import { InlineError } from "./states";
import styles from "./owner-dashboard.module.css";

export const isActive = (job?: SiteJob) =>
  job?.status === "PENDING" || job?.status === "RUNNING";

function time(value: string | null) {
  return value
    ? new Date(value).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "";
}

function summary(job: SiteJob) {
  const r = job.result ?? {};
  if (job.kind === "build_variant") {
    const status = String(r.status ?? "").toLowerCase();
    return r.status === "REJECTED"
      ? `v${r.version} was rejected by the parity check and not published`
      : `v${r.version} ${status} · ${r.products} products from ${r.pages} pages`;
  }
  if (job.kind === "label_sessions")
    return `Labeled ${r.labeled ?? 0} session${r.labeled === 1 ? "" : "s"}`;
  const side = (key: string) => {
    const value = r[key] as { passed?: number; eligible?: number } | undefined;
    return `${value?.passed ?? 0}/${value?.eligible ?? 0}`;
  };
  return `Original ${side("original")} · agent lane ${side("variant")}`;
}

/** The latest job of one kind, as a one-line status. Renders nothing before any run. */
export function JobStatus({ job }: { job?: SiteJob }) {
  if (!job) return null;
  if (job.status === "PENDING")
    return (
      <p className={styles.jobLine} role="status">
        <LoaderCircle size={13} className="animate-spin" aria-hidden="true" />
        Queued · waiting for the jobs worker
      </p>
    );
  if (job.status === "RUNNING")
    return (
      <p className={styles.jobLine} role="status">
        <LoaderCircle size={13} className="animate-spin" aria-hidden="true" />
        Running since {time(job.started_at)}
      </p>
    );
  if (job.status === "FAILED")
    return (
      <p className={styles.jobLine} data-tone="danger" role="status">
        <CircleAlert size={13} aria-hidden="true" />
        <span>
          Last run failed{job.detail ? `: ${job.detail}` : ""}
          <span className={styles.jobTime}> · {time(job.finished_at)}</span>
        </span>
      </p>
    );
  return (
    <p className={styles.jobLine} data-tone="success" role="status">
      <Check size={13} aria-hidden="true" />
      <span>
        {summary(job)}
        <span className={styles.jobTime}> · {time(job.finished_at)}</span>
      </span>
    </p>
  );
}

export function JobButton({
  job,
  label,
  onStart,
  disabled,
  variant = "default",
}: {
  job?: SiteJob;
  label: string;
  onStart: () => void;
  disabled?: boolean;
  variant?: "default" | "outline";
}) {
  const active = isActive(job);
  return (
    <Button
      size="sm"
      variant={variant}
      disabled={disabled || active}
      onClick={onStart}
    >
      {active && (
        <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />
      )}
      {active ? (job?.status === "PENDING" ? "Queued" : "Running") : label}
    </Button>
  );
}

const STATUS_LABEL: Record<DashboardVariant["status"], string> = {
  PUBLISHED: "Live",
  DRAFT: "Draft",
  REJECTED: "Rejected",
  SUPERSEDED: "Replaced",
};

export function LanePanel({
  variants,
  job,
  onBuild,
  onPublish,
}: {
  variants: DashboardVariant[];
  job?: SiteJob;
  onBuild: () => void;
  onPublish: (version: number) => void;
}) {
  const live = variants.find((v) => v.status === "PUBLISHED");
  return (
    <section
      className={`${styles.shell} ${styles.section}`}
      aria-labelledby="lane-title"
    >
      <div className={`${styles.card} ${styles.lanePanel}`}>
        <div className={styles.laneIntro}>
          <span className={styles.laneIcon} aria-hidden="true">
            <Rocket size={20} />
          </span>
          <h2 id="lane-title">Agent lane</h2>
          <p>
            {live
              ? `Version ${live.version} is live with ${live.products} products. AI agents get it at your normal URLs; people and search engines still see your site.`
              : "Build a clean version of your site for AI agents. It goes live only if every price matches your site."}
          </p>
          <div className={styles.laneActions}>
            <JobButton
              job={job}
              label={live ? "Rebuild agent lane" : "Build agent lane"}
              onStart={onBuild}
            />
          </div>
          <JobStatus job={job} />
        </div>
        <div className={styles.versions}>
          <p className={styles.kicker}>Versions</p>
          {variants.length ? (
            <ul>
              {variants.map((v) => (
                <li key={v.version}>
                  <span className={styles.versionNo}>v{v.version}</span>
                  <span className="min-w-0">
                    <span className={styles.versionMeta}>
                      <span
                        className={styles.versionStatus}
                        data-status={v.status}
                      >
                        {STATUS_LABEL[v.status]}
                      </span>
                      <span>
                        {v.products} products · {v.pages} pages
                      </span>
                    </span>
                    <span className={styles.versionParity}>
                      {v.parity_passed ? (
                        <ShieldCheck size={12} aria-hidden="true" />
                      ) : (
                        <X size={12} aria-hidden="true" />
                      )}
                      Parity {v.parity_passed ? "passed" : "failed"} ·{" "}
                      {time(v.created_at)}
                    </span>
                  </span>
                  {v.status === "DRAFT" && v.parity_passed && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onPublish(v.version)}
                    >
                      Publish
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.versionsEmpty}>
              No versions yet. Each build is kept here, including rejected ones,
              so you can see why.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

export function AddSiteForm({
  token,
  onCreated,
  onCancel,
}: {
  token: string;
  onCreated: (site: DashboardSite) => void;
  onCancel?: () => void;
}) {
  const [form, setForm] = useState({ name: "", host: "", origin: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const field =
    (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((current) => ({ ...current, [key]: e.target.value }));
  return (
    <div className={styles.shell}>
      <form
        className={`${styles.card} ${styles.cardBody} ${styles.addSite}`}
        onSubmit={async (event) => {
          event.preventDefault();
          setSaving(true);
          setError("");
          try {
            onCreated(await api.createSite(token, form));
          } catch (e) {
            setError(
              e instanceof Error ? e.message : "Could not add the site.",
            );
          } finally {
            setSaving(false);
          }
        }}
      >
        <div className={styles.cardHead}>
          <h2>Add a site</h2>
          {onCancel && (
            <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
        <div className={styles.addGrid}>
          <label>
            Site name
            <input
              className="field mt-2"
              value={form.name}
              onChange={field("name")}
              placeholder="Northstar Shoes"
              required
              maxLength={200}
            />
          </label>
          <label>
            Public host
            <input
              className="field mt-2"
              value={form.host}
              onChange={field("host")}
              placeholder="shop.example.com"
              required
              maxLength={253}
              autoCapitalize="none"
              spellCheck={false}
            />
            <span className={styles.hint}>
              The domain visitors use. Point it at the AgentLane router.
            </span>
          </label>
          <label>
            Origin
            <input
              className="field mt-2"
              value={form.origin}
              onChange={field("origin")}
              placeholder="https://origin.example.com"
              required
              maxLength={2048}
              type="url"
              autoCapitalize="none"
              spellCheck={false}
            />
            <span className={styles.hint}>
              Where your site is served today. The router forwards people here
              unchanged.
            </span>
          </label>
        </div>
        {error && (
          <div className="mt-4">
            <InlineError>{error}</InlineError>
          </div>
        )}
        <div className="mt-5">
          <Button disabled={saving}>
            {saving ? (
              <LoaderCircle
                size={14}
                className="animate-spin"
                aria-hidden="true"
              />
            ) : (
              <Plus size={14} aria-hidden="true" />
            )}
            Add site
          </Button>
        </div>
      </form>
    </div>
  );
}
