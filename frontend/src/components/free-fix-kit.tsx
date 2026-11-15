"use client";

import { useCallback, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Copy,
  Download,
  FileCode2,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { Button } from "./ui/button";
import { InlineError } from "./states";

export function FreeFixKit({ token }: { token: string }) {
  const load = useCallback(() => api.fixPreview(token), [token]);
  const { data, error, retry } = useResource(load);
  const [copied, setCopied] = useState("");
  const [copyError, setCopyError] = useState("");
  async function copy(key: string, content: string) {
    setCopyError("");
    try {
      await navigator.clipboard.writeText(content);
      setCopied(key);
    } catch {
      setCopyError(
        "Clipboard unavailable. Select and copy the preview text below.",
      );
    }
  }
  if (error)
    return (
      <section className="surface mt-10 p-5">
        <InlineError>
          {error.message}{" "}
          <button type="button" className="underline" onClick={retry}>
            Retry fix preview
          </button>
        </InlineError>
      </section>
    );
  if (!data)
    return (
      <div
        className="skeleton mt-14 h-48 rounded-[20px] motion-reduce:animate-none"
        role="status"
        aria-label="Preparing your free fixes"
      />
    );
  const count = data.fixes.length + data.assets.length;
  return (
    <section className="mt-16 sm:mt-20" aria-label="Your free Fix Kit sample">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow text-primary">
            A useful first step · yours to keep
          </p>
          <h2 className="display-md mt-2">
            Don’t just find it. <span className="mark-lime">Fix it.</span>
          </h2>
          <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted-foreground">
            {count
              ? `${count} ready-to-use ${count === 1 ? "fix" : "fixes"}, grounded in your scan. Copy a prompt into your coding assistant, or use a validated asset draft.`
              : "We need confirmed issues or usable page data before we can generate a useful sample. We won’t invent a fix."}
          </p>
        </div>
        {count > 0 && (
          <span className="rounded-full bg-success-soft px-3 py-1.5 text-[12px] font-bold text-success">
            Included free
          </span>
        )}
      </header>
      {data.fixes.length > 0 && (
        <div className="surface overflow-hidden">
          <h3 className="flex items-center gap-3 border-b px-5 py-4 text-[16px]">
            <span className="icon-tile size-9 rounded-xl">
              <Wrench size={16} />
            </span>
            Prioritized fixes{" "}
            <span className="ml-auto rounded-full bg-muted px-2.5 py-1 font-mono text-[12px] font-medium text-muted-foreground">
              {data.fixes.length} FREE
            </span>
          </h3>
          <div className="divide-y px-5">
            {data.fixes.map((fix, index) => (
              <details key={fix.key} className="group/fix" open={index === 0}>
                <summary className="flex min-h-16 cursor-pointer list-none items-center gap-4 py-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft font-mono text-[12px] font-semibold text-signal">
                    0{index + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="eyebrow block">
                      {fix.category} · {fix.severity.toLowerCase()} priority
                    </span>
                    <span className="mt-1 block text-[15px] font-semibold">
                      {fix.title}
                    </span>
                  </span>
                  <ChevronDown
                    size={14}
                    className="shrink-0 transition-transform group-open/fix:rotate-180"
                  />
                </summary>
                <div className="space-y-3 pb-6 sm:pl-12">
                  <p className="text-[14px] leading-6 text-muted-foreground">
                    {fix.recommendation}
                  </p>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      void copy(fix.key, fix.prompts.coding_assistant)
                    }
                  >
                    {copied === fix.key ? (
                      <Check size={13} />
                    ) : (
                      <Copy size={13} />
                    )}
                    {copied === fix.key
                      ? "Copied"
                      : "Copy coding-assistant prompt"}
                  </Button>
                  <details>
                    <summary className="cursor-pointer py-2 text-[13px] font-semibold text-foreground">
                      Read the complete prompt
                    </summary>
                    <pre
                      className="code-panel mt-2 max-h-64 overflow-auto"
                      tabIndex={0}
                    >
                      {fix.prompts.coding_assistant}
                    </pre>
                  </details>
                  <p className="text-[12px] leading-5 text-muted-foreground">
                    Includes the observed issue, constraints and verification
                    steps. Review changes before deploying.{" "}
                    {fix.template_version}
                  </p>
                </div>
              </details>
            ))}
          </div>
        </div>
      )}
      {data.assets.length > 0 && (
        <div className="surface mt-5 overflow-hidden">
          <h3 className="flex items-center gap-3 border-b px-5 py-4 text-[16px]">
            <span className="icon-tile size-9 rounded-xl" data-tone="lime">
              <FileCode2 size={16} />
            </span>
            Assets grounded in your crawl
          </h3>
          <div className="divide-y px-5">
            {data.assets.map((asset) => (
              <details key={asset.key} className="group/asset">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-4 text-[14px] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
                  <span className="font-mono font-medium">
                    {asset.filename}
                  </span>
                  <ChevronDown
                    size={14}
                    className="group-open/asset:rotate-180"
                  />
                </summary>
                <div className="space-y-3 pb-6">
                  <p className="text-[14px] leading-6">{asset.placement}</p>
                  <p className="text-[12px] leading-5 text-muted-foreground">
                    Validated structure · {asset.provenance}. Review facts
                    before publishing.
                  </p>
                  <pre
                    className="code-panel max-h-64 overflow-auto"
                    tabIndex={0}
                  >
                    {asset.content}
                  </pre>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => void copy(asset.key, asset.content)}
                    >
                      <Copy size={13} />
                      {copied === asset.key ? "Copied" : "Copy asset"}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        const url = URL.createObjectURL(
                          new Blob([asset.content], { type: asset.media_type }),
                        );
                        const anchor = document.createElement("a");
                        anchor.href = url;
                        anchor.download = asset.filename;
                        document.body.appendChild(anchor);
                        anchor.click();
                        anchor.remove();
                        setTimeout(() => URL.revokeObjectURL(url), 1000);
                      }}
                    >
                      <Download size={13} /> Download draft
                    </Button>
                  </div>
                </div>
              </details>
            ))}
          </div>
        </div>
      )}
      {copyError && (
        <div className="mt-3">
          <InlineError>{copyError}</InlineError>
        </div>
      )}
      {count > 0 && (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-[20px] bg-accent-soft px-5 py-4">
          <p className="text-[14px] font-medium leading-5 text-foreground">
            {data.remaining_fixes > 0 || data.remaining_assets > 0
              ? `${data.remaining_fixes}${data.truncated ? "+" : ""} more fixes · ${data.remaining_assets} more asset drafts in the full kit.`
              : "Go further with detailed evidence, exports and 30 days of same-domain re-scans."}
          </p>
          <a
            href="#full-fix-kit"
            className="inline-flex min-h-10 items-center gap-2 rounded-full bg-card px-4 text-[14px] font-semibold text-signal shadow-[var(--shadow-card)] hover:bg-muted"
          >
            Explore the full Fix Kit <ArrowRight size={13} />
          </a>
        </div>
      )}
    </section>
  );
}
