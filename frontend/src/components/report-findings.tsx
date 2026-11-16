"use client";

import { useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  ChevronDown,
  Copy,
  Download,
  FileCode2,
  LockKeyhole,
} from "lucide-react";
import type {
  CustomerFix,
  FreeFixPreview,
  FreeReportInsight,
} from "@/lib/types";
import { Button } from "./ui/button";

const PROMPT_TABS = [
  ["coding_assistant", "Coding assistant"],
  ["general_llm", "General AI"],
  ["developer_ticket", "Dev ticket"],
] as const;

export function severityLabel(severity: string) {
  const value = severity.toUpperCase();
  if (value === "CRITICAL" || value === "HIGH")
    return {
      label: value === "CRITICAL" ? "Critical" : "High",
      tone: "danger",
    };
  if (value === "MEDIUM") return { label: "Medium", tone: "warning" };
  return { label: "Low", tone: "muted" };
}

export function isHighSeverity(severity: string) {
  return ["CRITICAL", "HIGH"].includes(severity.toUpperCase());
}

function safeHttpUrl(value: string | null | undefined) {
  return value && /^https?:\/\//i.test(value) ? value : null;
}

/** Plain-language reason a finding matters, so the fix isn't just a code snippet. */
export function whyInsightMatters(insight: FreeReportInsight) {
  const finding = `${insight.title} ${insight.description}`.toLowerCase();
  if (
    /accessible name|accessible label|form field|button.*name|link.*name/.test(
      finding,
    )
  )
    return "An accessible name tells an agent what a control does before it chooses to use it.";
  if (/keyboard|clickable|native semantics/.test(finding))
    return "Native controls expose familiar roles and behavior that browser tools can identify more reliably.";
  if (/javascript|rendered comparison|server-render/.test(finding))
    return "If key content appears only after scripts run, some crawlers and agents may miss it or wait longer to understand the page.";
  if (
    /challenge|captcha|bot protection|restricted|crawler access/.test(finding)
  )
    return "A challenge or access rule can stop an automated visitor before it reaches the page. This result reflects only the evidence in this scan.";
  if (/robots/.test(finding))
    return "The inspected robots rule affects this scanner’s access; other agents may follow different rules. Review the specific rule before changing it.";
  if (/sitemap/.test(finding))
    return "A sitemap helps crawlers discover pages directly, alongside your internal links.";
  if (/llms\.txt/.test(finding))
    return "llms.txt is an optional proposal. Its absence alone does not show that agents cannot discover or use your site.";
  if (/json-ld|structured data|schema/.test(finding))
    return "Valid structured data makes products, prices and organizations easier for compatible tools to interpret. It doesn’t replace readable page content.";
  if (/heading|h1/.test(finding))
    return "Headings give a page an outline. Agents use it to find the section that answers a question.";
  if (/http|response|redirect|error/.test(finding))
    return "Unexpected responses or redirects can stop an agent from reaching the content it was looking for.";
  const category = insight.category.toLowerCase();
  if (/discover|crawl/.test(category))
    return "Agents can only use pages they can discover and access.";
  if (/structured|schema|content/.test(category))
    return "Clear structure helps agents identify the information a page contains.";
  if (/usability|navigation|interaction|agent/.test(category))
    return "Accessible names and predictable controls help agents choose the right interaction.";
  return "This may affect an agent’s ability to find, understand or use this part of the site.";
}

function PromptPanel({ fix }: { fix: CustomerFix }) {
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState<"" | "done" | "failed">("");
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const id = useId();
  const [key] = PROMPT_TABS[active];
  const prompt = fix.prompts[key];
  const select = (index: number) => {
    setActive(index);
    setCopied("");
  };
  const onKeyDown = (event: KeyboardEvent) => {
    const step =
      event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (active + step + PROMPT_TABS.length) % PROMPT_TABS.length;
    select(next);
    tabs.current[next]?.focus();
  };
  return (
    <div className="rounded-2xl border p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          role="tablist"
          aria-label="Prompt for"
          onKeyDown={onKeyDown}
          className="flex max-w-full flex-wrap gap-0.5 rounded-[11px] bg-muted p-[3px]"
        >
          {PROMPT_TABS.map(([tabKey, label], index) => (
            <button
              key={tabKey}
              ref={(node) => {
                tabs.current[index] = node;
              }}
              type="button"
              role="tab"
              id={`${id}-${tabKey}`}
              aria-selected={index === active}
              aria-controls={`${id}-panel`}
              tabIndex={index === active ? 0 : -1}
              onClick={() => select(index)}
              className="min-h-8 cursor-pointer rounded-lg px-2 text-[12.5px] font-medium sm:px-2.5 sm:text-[13px] text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-selected:bg-card aria-selected:text-foreground aria-selected:shadow-[0_1px_2px_#0e10131a] dark:aria-selected:bg-border"
            >
              {label}
            </button>
          ))}
        </div>
        <Button
          type="button"
          variant="ink"
          size="sm"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(prompt);
              setCopied("done");
            } catch {
              setCopied("failed");
            }
          }}
        >
          {copied === "done" ? <Check size={14} /> : <Copy size={14} />}
          {copied === "done" ? "Prompt copied" : "Copy prompt"}
        </Button>
      </div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${key}`}>
        <p className="mt-3 text-[13.5px] leading-6 text-muted-foreground">
          {copied === "failed"
            ? "Clipboard unavailable. Open the full prompt below and copy it."
            : "Includes the page, the evidence, constraints that keep your design and behavior, and how to verify the fix."}
        </p>
        <details className="group/prompt mt-1">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 py-1.5 text-[13px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            Read the full prompt
            <ChevronDown
              size={13}
              className="transition-transform group-open/prompt:rotate-180"
            />
          </summary>
          <pre className="code-panel mt-2 max-h-64 overflow-auto" tabIndex={0}>
            {prompt}
          </pre>
          <p className="mt-2 text-[12px] text-muted-foreground">
            Review changes before deploying · {fix.template_version}
          </p>
        </details>
      </div>
    </div>
  );
}

function looksLikeCode(text: string) {
  return /^\s*</.test(text);
}

function FindingRow({
  insight,
  index,
  fix,
  mode,
  seenOn = [],
}: {
  insight: FreeReportInsight;
  index: number;
  fix?: CustomerFix;
  mode: "locked" | "unlocked";
  seenOn?: string[];
}) {
  const severity = severityLabel(insight.severity);
  const page = safeHttpUrl(fix?.url ?? insight.evidence_url);
  const evidence = fix?.evidence || insight.evidence_summary;
  // "Example inspected element: <button>" reads better as just the element.
  const found = evidence?.replace(/^example inspected element:\s*/i, "");
  const locked = mode === "locked" && !fix;
  const morePages = seenOn.filter((url) => url !== page).length;
  return (
    <details className="report-finding group/finding" open={index === 0}>
      <summary className="flex min-h-[72px] cursor-pointer list-none items-center gap-3 px-5 py-4 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40 sm:gap-4 sm:px-6">
        <span className="w-6 shrink-0 font-mono text-[12.5px] text-muted-foreground">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12.5px] text-muted-foreground">
            <span
              className="report-severity font-semibold"
              data-tone={severity.tone}
            >
              {severity.label}
            </span>{" "}
            · {insight.category}
          </span>
          <span className="mt-0.5 block text-[15.5px] font-semibold leading-snug sm:text-[16.5px]">
            {insight.title}
          </span>
        </span>
        {fix ? (
          <span className="shrink-0 rounded-[7px] bg-[var(--brand-lime)] px-2 py-0.5 text-[12px] font-semibold text-[var(--brand-ink)]">
            Free fix
          </span>
        ) : locked ? (
          <span className="inline-flex shrink-0 items-center gap-1.5 text-[12.5px] text-muted-foreground">
            <LockKeyhole size={13} aria-hidden="true" />
            <span className="max-[479px]:sr-only">In the Fix Kit</span>
          </span>
        ) : null}
        <ChevronDown
          size={16}
          className="shrink-0 text-muted-foreground transition-transform group-open/finding:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="space-y-4 px-4 pb-6 sm:pl-[64px] sm:pr-6">
        <p className="text-[14.5px] leading-6 text-muted-foreground">
          {whyInsightMatters(insight)}
        </p>
        {(page || found || insight.recommendation) && (
          <div className="report-diff">
            {page && (
              <a
                href={page}
                target="_blank"
                rel="noopener noreferrer"
                title={page}
                className="report-diff-page"
              >
                <span className="shrink-0">Seen on</span>
                <span className="truncate font-mono">
                  {page.replace(/^https?:\/\//, "")}
                </span>
                <ArrowUpRight
                  size={12}
                  className="shrink-0"
                  aria-hidden="true"
                />
                {morePages > 0 && (
                  <span className="shrink-0">
                    and {morePages} more {morePages === 1 ? "page" : "pages"}
                  </span>
                )}
              </a>
            )}
            {found && (
              <div className="report-diff-row" data-kind="found">
                <span>Found</span>
                <code>{found}</code>
              </div>
            )}
            {insight.recommendation && (
              <div className="report-diff-row" data-kind="fix">
                <span>Fix</span>
                {looksLikeCode(insight.recommendation) ? (
                  <code>{insight.recommendation}</code>
                ) : (
                  <p>{insight.recommendation}</p>
                )}
              </div>
            )}
          </div>
        )}
        {fix && <PromptPanel fix={fix} />}
        {locked && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-2xl bg-muted px-4 py-3 text-[13.5px] text-muted-foreground">
            <LockKeyhole size={14} aria-hidden="true" />
            The Fix Kit adds the affected page, the evidence and a ready prompt.
            <a
              href="#full-fix-kit"
              className="font-semibold text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
            >
              See what’s included
            </a>
          </p>
        )}
        {mode === "unlocked" && (
          <a
            href="#fix-center"
            className="inline-flex items-center gap-1.5 text-[13.5px] font-semibold underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            Prompts and progress in your Fix Center
            <ArrowDown size={13} aria-hidden="true" />
          </a>
        )}
      </div>
    </details>
  );
}

/** One prioritized list: each finding carries why it matters, where it was seen,
 * how to fix it and, when the free sample or a purchase covers it, a ready prompt. */
export function FindingList({
  insights,
  fixes = [],
  mode,
  pages = {},
}: {
  insights: FreeReportInsight[];
  fixes?: CustomerFix[];
  mode: "locked" | "unlocked";
  pages?: Record<string, string[]>;
}) {
  const fixFor = new Map(fixes.map((fix) => [fix.title, fix]));
  return (
    <div className="surface divide-y overflow-hidden">
      {insights.map((insight, index) => (
        <FindingRow
          key={`${index}-${insight.title}`}
          insight={insight}
          index={index}
          fix={mode === "locked" ? fixFor.get(insight.title) : undefined}
          mode={mode}
          seenOn={pages[insight.title]}
        />
      ))}
    </div>
  );
}

export function AssetDrafts({ assets }: { assets: FreeFixPreview["assets"] }) {
  const [copied, setCopied] = useState("");
  if (!assets.length) return null;
  return (
    <div className="surface mt-5 overflow-hidden">
      <h3 className="flex items-center gap-3 border-b px-5 py-4 text-[16px] sm:px-6">
        <span className="icon-tile size-9 rounded-xl" data-tone="lime">
          <FileCode2 size={16} />
        </span>
        Free asset drafts from your crawl
      </h3>
      <div className="divide-y px-5 sm:px-6">
        {assets.map((asset) => (
          <details key={asset.key} className="group/asset">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 py-4 text-[14px] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
              <span className="font-mono font-medium">{asset.filename}</span>
              <ChevronDown
                size={14}
                className="group-open/asset:rotate-180"
                aria-hidden="true"
              />
            </summary>
            <div className="space-y-3 pb-6">
              <p className="text-[14px] leading-6">{asset.placement}</p>
              <p className="text-[12px] leading-5 text-muted-foreground">
                Validated structure · {asset.provenance}. Review facts before
                publishing.
              </p>
              <pre className="code-panel max-h-64 overflow-auto" tabIndex={0}>
                {asset.content}
              </pre>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(asset.content);
                      setCopied(asset.key);
                    } catch {
                      setCopied("");
                    }
                  }}
                >
                  {copied === asset.key ? (
                    <Check size={13} />
                  ) : (
                    <Copy size={13} />
                  )}
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
  );
}
