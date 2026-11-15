import { ArrowUpRight, Globe2, LoaderCircle, ShieldCheck } from "lucide-react";
import { Brand } from "./product-ui";

export function ScanTransition({
  website,
  reportPath,
}: {
  website?: string;
  reportPath?: string;
}) {
  return (
    <div className="report-frame min-h-dvh bg-background text-foreground">
      <header className="nav-glass border-b border-border/60">
        <div className="mx-auto flex min-h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-8">
          <Brand />
          <span className="hidden items-center gap-1.5 text-[13px] font-medium text-muted-foreground sm:inline-flex">
            <ShieldCheck size={14} className="text-primary" /> Read-only website
            scan
          </span>
        </div>
      </header>
      <main className="mx-auto flex max-w-2xl flex-col items-center px-4 py-16 text-center sm:px-8 sm:py-24">
        <div
          className="relative grid size-28 place-items-center"
          aria-hidden="true"
        >
          <span className="absolute inset-0 rounded-full bg-accent-soft motion-safe:animate-ping motion-safe:[animation-duration:2.4s]" />
          <span className="absolute inset-3 rounded-full bg-lime/60" />
          <span className="icon-tile relative size-14 rounded-2xl shadow-[var(--shadow-float)]">
            <Globe2 size={26} strokeWidth={1.8} />
          </span>
        </div>
        <p className="eyebrow mt-10">Your website, through an agent’s eyes</p>
        <h1 className="display-lg mt-3">Preparing your report</h1>
        {website && (
          <p className="mt-5 max-w-full break-all rounded-full bg-muted px-4 py-1.5 font-mono text-[13px] font-medium text-foreground">
            {website}
          </p>
        )}
        <div className="surface mt-10 w-full p-6 text-left sm:p-7">
          <div
            className="flex items-start gap-4"
            role="status"
            aria-live="polite"
          >
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-signal">
              <LoaderCircle
                size={21}
                className="animate-spin motion-reduce:animate-none"
              />
            </span>
            <div>
              <p className="text-[16px] font-semibold">
                {reportPath
                  ? "Opening your report…"
                  : website
                    ? "Creating your report link…"
                    : "Loading your report…"}
              </p>
              <p className="mt-1 text-[14px] leading-6 text-muted-foreground">
                You’ll see the scan’s progress here as soon as it starts.
              </p>
            </div>
          </div>
          <div className="mt-5 flex min-h-7 flex-wrap items-center justify-between gap-3 border-t pt-4 text-[13px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-success" /> No forms
              submitted. No changes to your site.
            </span>
            {reportPath && (
              <a
                href={reportPath}
                className="inline-flex shrink-0 items-center gap-1 font-semibold text-primary underline-offset-4 hover:underline"
              >
                Open report <ArrowUpRight size={13} />
              </a>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
