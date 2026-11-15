"use client";
import { useCallback, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  LoaderCircle,
  LockKeyhole,
  MailCheck,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { Button } from "./ui/button";
import { DomainVerification } from "./domain-verification";
import { InlineError } from "./states";

export function ReportUnlock({
  token,
  website,
  scoreAvailable,
  developmentSkipAvailable,
  onUnlocked,
}: {
  token: string;
  website: string;
  scoreAvailable: boolean;
  developmentSkipAvailable?: boolean;
  onUnlocked: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!scoreAvailable)
    return (
      <section className="surface mt-10 p-6 sm:p-8">
        <h2 className="display-md">Let’s get useful evidence first.</h2>
        <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted-foreground">
          We won’t ask you to pay for a report without enough inspected page
          evidence. Check the access issue, then retry. Your verified email is
          still required.
        </p>
        <Button
          className="mt-6"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              const scan = await api.startFreeScan(website);
              if (!/^\/free-reports\/[A-Za-z0-9_-]+$/.test(scan.report_path))
                throw new Error("Invalid report link");
              window.location.assign(scan.report_path);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Could not retry");
              setBusy(false);
            }
          }}
        >
          {" "}
          {busy && <LoaderCircle className="animate-spin" size={14} />} Retry
          verified scan
        </Button>
        {error && (
          <div className="mt-4">
            <InlineError>{error}</InlineError>
          </div>
        )}
      </section>
    );
  return (
    <section
      className="report-unlock mt-14 scroll-mt-24 rounded-[28px] shadow-[var(--shadow-float)]"
      aria-label="Unlock full report"
      id="full-fix-kit"
    >
      <div className="grid gap-8 p-7 sm:p-10 md:grid-cols-[1fr_auto] md:items-center md:gap-12">
        <div>
          <p className="eyebrow text-white">Your next step</p>
          <h2 className="display-md mt-3 text-white">
            A starting point is good.
            <br />
            The complete Fix Kit is <span className="mark-lime">$19.</span>
          </h2>
          <p className="mt-4 max-w-lg text-[15px] leading-7 text-white/90">
            Keep your free sample. Unlock the remaining findings, detailed page
            evidence, copy-ready developer prompts, validated asset drafts, and
            downloadable reports. Re-scan this domain free for 30 days.
          </p>
          <div className="mt-5 flex flex-wrap gap-2 text-[13px] font-semibold text-white">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5">
              <Check size={14} className="text-[var(--brand-uv-light)]" />{" "}
              One-time payment
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5">
              <Check size={14} className="text-[var(--brand-uv-light)]" />{" "}
              Same-domain re-scans for 30 days
            </span>
          </div>
        </div>
        <div className="rounded-[22px] bg-card p-6 text-foreground shadow-[var(--shadow-float)] md:min-w-64 md:text-center">
          <p className="mb-4 font-display text-[56px] font-extrabold leading-none tracking-[-.03em]">
            $19
            <span className="ml-1.5 font-sans text-[13px] font-semibold tracking-normal text-muted-foreground">
              USD
            </span>
          </p>
          <Button
            variant="lime"
            size="lg"
            className="w-full"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                const result = await api.checkout(token);
                const url = new URL(result.url);
                if (
                  url.protocol !== "https:" ||
                  url.hostname !== "checkout.stripe.com"
                )
                  throw new Error("Unexpected payment link. Please retry.");
                window.location.assign(url.toString());
              } catch (e) {
                if (
                  e instanceof ApiError &&
                  e.status === 409 &&
                  e.message.includes("already unlocked")
                ) {
                  window.location.reload();
                  return;
                }
                setError(
                  e instanceof Error ? e.message : "Could not open checkout.",
                );
                setBusy(false);
              }
            }}
          >
            {busy ? (
              <LoaderCircle size={14} className="animate-spin" />
            ) : (
              <LockKeyhole size={14} />
            )}{" "}
            Unlock full report <ArrowRight size={14} />
          </Button>
          <p className="mt-3 text-[12px] font-medium text-muted-foreground">
            Secure checkout with Stripe
          </p>
          {developmentSkipAvailable && (
            <Button
              variant="outline"
              className="mt-3 w-full"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await api.skipPayment(token);
                  onUnlocked();
                } catch (e) {
                  setError(
                    e instanceof Error ? e.message : "Could not skip payment.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Skip payment (development)
            </Button>
          )}
        </div>
      </div>
      {error && (
        <div className="px-7 pb-7 sm:px-10">
          <InlineError>{error}</InlineError>
        </div>
      )}
      <p className="report-unlock-note px-7 py-4 text-[13px] leading-5 sm:px-10">
        AI browser-agent testing is coming Christmas 2026 and is not included in
        this purchase. Access updates after Stripe confirms payment; a success
        redirect alone never unlocks a report.
      </p>
    </section>
  );
}

export function ReportVerification({
  token,
  onVerified,
}: {
  token: string;
  onVerified: () => void;
}) {
  const load = useCallback(() => api.reportTarget(token), [token]);
  const { data, error } = useResource(load);
  const [open, setOpen] = useState(true);
  return (
    <main className="mx-auto max-w-xl px-4 py-20 text-center sm:py-28">
      <span className="icon-tile mx-auto mb-6 size-14 rounded-2xl">
        <MailCheck size={24} strokeWidth={1.8} />
      </span>
      <p className="chip">
        <span className="chip-dot" aria-hidden="true" />
        Your website report
      </p>
      <h1 className="display-md mt-5">Verify your email to continue.</h1>
      <p className="lede mx-auto mt-4 max-w-md">
        Reports are available only to verified website contacts. Your previous
        email session may have expired.
      </p>
      {error && (
        <div className="mt-5 text-left">
          <InlineError>{error.message}</InlineError>
        </div>
      )}
      {data && (
        <>
          <Button size="lg" className="mt-8" onClick={() => setOpen(true)}>
            Verify your email
          </Button>
          <DomainVerification
            key={data.website_url}
            website={data.website_url}
            open={open}
            onClose={() => setOpen(false)}
            onVerified={onVerified}
          />
        </>
      )}
      <Link
        className="mt-6 inline-block text-[14px] font-medium text-muted-foreground underline underline-offset-4 hover:text-foreground"
        href="/"
      >
        Back to homepage
      </Link>
    </main>
  );
}
