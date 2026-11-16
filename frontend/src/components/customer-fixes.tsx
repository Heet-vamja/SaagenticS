"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  Download,
  FileCode2,
  LoaderCircle,
  RotateCw,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import type { CustomerFix, FixAction, RobotsPreset } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { Button } from "./ui/button";
import { InlineError } from "./states";

function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const statusLabels = {
  OPEN: "Open",
  PROMPT_COPIED: "Prompt copied",
  FIX_APPLIED: "Applied · awaiting rescan",
  STILL_FAILING: "Still failing",
};

/** The fix engine's categories, named like the report's score areas. */
function fixArea(category: string) {
  const areas: Record<string, string> = {
    Actionability: "Agent usability",
    Readability: "Content understanding",
  };
  return areas[category] ?? category;
}

export function CustomerFixes({ token }: { token: string }) {
  const router = useRouter();
  const [preset, setPreset] = useState<RobotsPreset>("keep_existing");
  const [variant, setVariant] =
    useState<keyof CustomerFix["prompts"]>("coding_assistant");
  const [visibleCount, setVisibleCount] = useState(5);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const load = useCallback(() => api.fixCenter(token, preset), [token, preset]);
  const { data, error, retry } = useResource(load);

  async function perform(key: string, action: () => Promise<void>) {
    setBusy(key);
    setActionError(null);
    try {
      await action();
      retry();
    } catch (failure) {
      setActionError(
        failure instanceof Error
          ? failure.message
          : "Could not complete this action. Please retry.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function record(event: FixAction, key = "") {
    await api.fixEvent(token, event, key);
  }

  if (!data && !error)
    return (
      <section className="mt-16 space-y-4" aria-label="Loading fixes">
        <div className="skeleton h-8 w-56" />
        <div className="skeleton h-40 w-full rounded-[20px]" />
      </section>
    );
  if (!data)
    return (
      <section className="mt-12">
        <InlineError>
          {error?.message}{" "}
          <button onClick={retry} className="underline">
            Retry fixes
          </button>
        </InlineError>
      </section>
    );
  const usefulAnswered = data.events.some((event) =>
    ["USEFUL", "NOT_USEFUL"].includes(event),
  );

  return (
    <section
      id="fix-center"
      className="mt-16 scroll-mt-24 sm:mt-20"
      aria-labelledby="fix-center-heading"
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow text-primary">From evidence to improvement</p>
          <h2 id="fix-center-heading" className="display-md mt-2">
            Your Fix Center
          </h2>
          <p className="mt-3 max-w-lg text-[15px] leading-7 text-muted-foreground">
            Give your developer a precise starting point. Review changes, deploy
            them, then verify the same checks again.
          </p>
        </div>
        <Button
          variant="ink"
          disabled={busy !== null}
          onClick={() =>
            perform("pack", async () =>
              saveFile(
                await api.downloadFixPack(token, preset),
                "agentlane-fix-pack.zip",
              ),
            )
          }
        >
          {busy === "pack" ? (
            <LoaderCircle size={14} className="animate-spin" />
          ) : (
            <Download size={14} />
          )}{" "}
          Download fix pack
        </Button>
      </div>
      {(error || actionError) && (
        <div className="mt-4" role="alert">
          <InlineError>{actionError ?? error?.message}</InlineError>
        </div>
      )}
      {data.comparison.total > 0 && (
        <section
          className="surface mt-7 overflow-hidden"
          aria-label="Rescan verification"
        >
          <div className="flex items-start gap-4 bg-success-soft p-5 sm:p-6">
            <span
              className="icon-tile size-10 shrink-0 rounded-xl"
              data-tone="lime"
            >
              <CheckCircle2 size={19} />
            </span>
            <div>
              <h3 className="text-[18px]">
                {data.comparison.confirmed} of {data.comparison.total} previous
                issues confirmed fixed
              </h3>
              <p className="mt-1 text-[14px] leading-6 text-foreground">
                {data.comparison.reason ??
                  "Only an explicit pass for the same rule and page counts as confirmed. Missing or inconclusive checks remain unverified."}
              </p>
              {data.comparison.score_delta !== null && (
                <p className="mt-2 inline-block rounded-full bg-card px-3 py-1 font-mono text-xs font-medium text-foreground">
                  Static score: {data.comparison.score_before} →{" "}
                  {data.comparison.score_after} (
                  {data.comparison.score_delta > 0 ? "+" : ""}
                  {data.comparison.score_delta})
                </p>
              )}
            </div>
          </div>
          <div className="divide-y px-5">
            {data.comparison.results.map((result) => (
              <div
                key={result.key}
                className="flex flex-col justify-between gap-1 py-3.5 text-[14px] sm:flex-row sm:items-center sm:gap-4"
              >
                <span>{result.title}</span>
                <span
                  className={`shrink-0 self-start rounded-full px-2.5 py-1 text-[12px] font-bold sm:self-auto ${result.status === "VERIFIED_FIXED" ? "bg-success-soft text-success" : "bg-muted text-muted-foreground"}`}
                >
                  {result.status === "VERIFIED_FIXED"
                    ? "Verified fixed"
                    : result.status === "STILL_FAILING"
                      ? "Still failing"
                      : "Not confirmed · insufficient evidence"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
      <div className="surface mt-7 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
          <h3 className="flex items-center gap-3 text-[16px]">
            <span className="icon-tile size-9 rounded-xl">
              <Wrench size={16} />
            </span>
            Prioritized fixes{" "}
            <span className="rounded-full bg-muted px-2.5 py-0.5 font-mono text-[12px] font-medium text-muted-foreground">
              {data.fixes.length}
            </span>
          </h3>
          <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
            Prompt for
            <select
              aria-label="Fix prompt format"
              value={variant}
              onChange={(event) =>
                setVariant(event.target.value as keyof CustomerFix["prompts"])
              }
              className="min-h-9 appearance-none rounded-full border bg-card py-1.5 pl-3.5 pr-9 font-medium text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              <option value="coding_assistant">Coding assistant</option>
              <option value="general_llm">General AI</option>
              <option value="developer_ticket">Dev ticket</option>
            </select>
          </label>
        </div>
        <div className="divide-y px-5">
          {data.fixes.slice(0, visibleCount).map((fix, index) => (
            <details key={fix.key} className="group/fix">
              <summary className="flex cursor-pointer list-none items-center gap-4 py-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft font-mono text-[12px] font-semibold text-signal">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="eyebrow block">
                    {fixArea(fix.category)} · {fix.severity.toLowerCase()}{" "}
                    priority
                  </span>
                  <span className="mt-1 block text-[15px] font-semibold">
                    {fix.title}
                  </span>
                  {fix.url && (
                    <span className="mt-0.5 block truncate font-mono text-[12px] text-muted-foreground">
                      {fix.url.replace(/^https?:\/\//, "")}
                    </span>
                  )}
                  <span
                    className={`mt-1.5 inline-block rounded-full px-2.5 py-0.5 text-[12px] font-bold ${fix.status === "FIX_APPLIED" ? "bg-accent-soft text-signal" : fix.status === "STILL_FAILING" ? "bg-warning-soft text-warning" : fix.status === "PROMPT_COPIED" ? "bg-action-soft text-foreground" : "bg-muted text-muted-foreground"}`}
                  >
                    {statusLabels[fix.status]}
                  </span>
                </span>
                <ChevronDown
                  size={15}
                  className="shrink-0 text-muted-foreground transition-transform group-open/fix:rotate-180"
                />
              </summary>
              <div className="space-y-4 pb-6 text-[14px] leading-6 sm:pl-12">
                <div className="rounded-2xl bg-muted p-4">
                  <p className="font-semibold">Observed evidence</p>
                  <p className="mt-1 whitespace-pre-wrap break-words text-muted-foreground">
                    {fix.evidence}
                  </p>
                  {fix.url && (
                    <p className="mt-2 break-all font-mono text-[12px] text-muted-foreground">
                      {fix.url}
                    </p>
                  )}
                </div>
                <div>
                  <p className="font-semibold">Suggested change</p>
                  <p className="mt-1 whitespace-pre-wrap break-words text-muted-foreground">
                    {fix.recommendation}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    disabled={busy !== null}
                    onClick={() =>
                      perform(fix.key, async () => {
                        await navigator.clipboard.writeText(
                          fix.prompts[variant],
                        );
                        setCopied(fix.key);
                        await record("PROMPT_COPIED", fix.key);
                      })
                    }
                  >
                    {copied === fix.key ? (
                      <Check size={13} />
                    ) : (
                      <Copy size={13} />
                    )}
                    {copied === fix.key ? "Prompt copied" : "Copy fix prompt"}
                  </Button>
                  <Button
                    variant="ghost"
                    className="max-w-full whitespace-normal text-center"
                    disabled={busy !== null || fix.status === "FIX_APPLIED"}
                    onClick={() =>
                      perform(fix.key, () => record("FIX_APPLIED", fix.key))
                    }
                  >
                    {fix.status === "FIX_APPLIED"
                      ? "Applied · verify with a rescan"
                      : "I’ve applied this fix"}
                  </Button>
                </div>
                <p className="text-[12px] leading-5 text-muted-foreground">
                  {fix.template_version} · Deterministic guidance. Copying or
                  applying a change does not confirm that it is fixed.
                </p>
                <details>
                  <summary className="cursor-pointer text-[13px] font-semibold text-foreground">
                    Preview prompt
                  </summary>
                  <pre tabIndex={0} className="code-panel mt-2">
                    {fix.prompts[variant]}
                  </pre>
                </details>
              </div>
            </details>
          ))}
        </div>
        {data.fixes.length === 0 && (
          <p className="p-5 text-[14px] leading-6 text-muted-foreground">
            No confirmed failing checks are available for fix prompts. Review
            scan coverage and inconclusive results before interpreting this as a
            clean bill of health.
          </p>
        )}
        {visibleCount < data.fixes.length && (
          <div className="border-t p-3 text-center">
            <Button
              variant="ghost"
              onClick={() => setVisibleCount((count) => count + 5)}
            >
              Show next {Math.min(5, data.fixes.length - visibleCount)} fixes
            </Button>
          </div>
        )}
        {data.truncated && (
          <p className="border-t p-4 text-[12px] text-muted-foreground">
            Showing the first 100 prioritized fixes in this bounded report.
          </p>
        )}
      </div>
      <div className="surface mt-5 overflow-hidden">
        <div className="border-b px-5 py-4">
          <h3 className="flex items-center gap-3 text-[16px]">
            <span className="icon-tile size-9 rounded-xl" data-tone="lime">
              <FileCode2 size={16} />
            </span>
            Assets grounded in your crawl
          </h3>
          <p className="mt-2 text-[14px] leading-6 text-muted-foreground">
            Validated drafts from observed public pages. Confirm accuracy before
            publishing.
          </p>
        </div>
        <div className="border-b px-5 py-4">
          <label htmlFor="robots-preset" className="text-[14px] font-semibold">
            Optional robots policy proposal
          </label>
          <select
            id="robots-preset"
            value={preset}
            onChange={(event) => setPreset(event.target.value as RobotsPreset)}
            className="field mt-2 block"
          >
            <option value="keep_existing">
              Keep existing policy · no proposal
            </option>
            <option value="allow_search">
              Allow AI search on sampled public pages
            </option>
            <option value="block_training">
              Block listed training bots; allow search on sampled pages
            </option>
          </select>
          <p className="mt-2 text-[12px] leading-5 text-muted-foreground">
            Choosing a preset only creates a file for owner review. Existing
            private paths and security restrictions must be preserved.
          </p>
        </div>
        <div className="divide-y px-5">
          {data.assets.map((asset) => (
            <details key={asset.key} className="group/asset">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-4 text-[14px] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-medium">
                    {asset.filename}
                  </span>
                  <span className="rounded-full bg-success-soft px-2.5 py-0.5 text-[12px] font-bold text-success">
                    Validated structure
                  </span>
                </span>
                <ChevronDown
                  size={14}
                  className="transition-transform group-open/asset:rotate-180"
                />
              </summary>
              <div className="pb-6 text-[14px] leading-6">
                <p>{asset.placement}</p>
                <p className="mt-2 text-[13px] text-muted-foreground">
                  Source: {asset.provenance}
                </p>
                <pre tabIndex={0} className="code-panel my-3">
                  {asset.content}
                </pre>
                <Button
                  variant="outline"
                  disabled={busy !== null}
                  onClick={() =>
                    perform(asset.key, async () =>
                      saveFile(
                        await api.downloadFixAsset(
                          token,
                          asset.filename,
                          preset,
                        ),
                        asset.filename,
                      ),
                    )
                  }
                >
                  <Download size={13} /> Download asset
                </Button>
              </div>
            </details>
          ))}
        </div>
        {data.assets.length === 0 && (
          <p className="p-5 text-[14px] text-muted-foreground">
            No validated assets could be generated from this crawl. Review the
            missing information below.
          </p>
        )}
      </div>
      {data.missing_information.length > 0 && (
        <details className="surface mt-5 px-5">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-4 text-[15px] font-semibold">
            Information still needed <ChevronDown size={14} />
          </summary>
          <ul className="list-disc space-y-2 pb-5 pl-4 text-[14px] leading-6 text-muted-foreground">
            {data.missing_information.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      )}
      <div className="mt-7 flex flex-col justify-between gap-5 rounded-[24px] bg-action-soft p-6 dark:bg-accent-soft sm:flex-row sm:items-center sm:p-8">
        <div>
          <h3 className="display-md text-[24px] sm:text-[28px]">
            Ready to verify an update?
          </h3>
          <p className="mt-2 max-w-lg text-[15px] leading-7 text-foreground/80">
            Start the same read-only scan and compare each previous issue
            against new evidence. Only explicit passes count as confirmed fixes.
          </p>
        </div>
        <Button
          size="lg"
          disabled={busy !== null}
          className="shrink-0"
          onClick={() =>
            perform("rescan", async () => {
              const next = await api.rescanFreeReport(token);
              router.push(next.report_path);
            })
          }
        >
          {busy === "rescan" ? (
            <LoaderCircle size={14} className="animate-spin" />
          ) : (
            <RotateCw size={14} />
          )}{" "}
          Re-scan to verify
        </Button>
      </div>
      <div className="surface mt-5 p-5 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[15px] font-medium">
            Did this report help you understand what to improve?
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={busy !== null || usefulAnswered}
              onClick={() => perform("feedback", () => record("USEFUL"))}
            >
              Yes
            </Button>
            <Button
              variant="ghost"
              disabled={busy !== null || usefulAnswered}
              onClick={() => perform("feedback", () => record("NOT_USEFUL"))}
            >
              Not yet
            </Button>
          </div>
        </div>
        {usefulAnswered && (
          <p
            role="status"
            className="mt-2 text-[14px] font-medium text-success"
          >
            Thanks — your feedback was saved.
          </p>
        )}
      </div>
    </section>
  );
}
