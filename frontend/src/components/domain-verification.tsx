"use client";
import { useCallback, useState } from "react";
import Link from "next/link";
import { ArrowRight, LoaderCircle, Mail, ShieldCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { InlineError } from "./states";

export function DomainVerification({
  website,
  open,
  onClose,
  onVerified,
}: {
  website: string;
  open: boolean;
  onClose: () => void;
  onVerified: () => void;
}) {
  const [email, setEmail] = useState("");
  const [useDifferentEmail, setUseDifferentEmail] = useState(false);
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState<{
    challenge_id?: string;
    email_hint: string;
  } | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => api.verificationStatus(website), [website]);
  const { data: status } = useResource(load);
  const domain = new URL(website).hostname.replace(/^www\./, "");
  async function requestEmail(candidateId?: string, hint?: string) {
    setSelectedCandidate(candidateId);
    try {
      setChallenge(
        await api.requestCode(
          website,
          candidateId ? undefined : email,
          candidateId,
        ),
      );
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.status === 503 &&
        status?.development_skip_available
      ) {
        setChallenge({ email_hint: hint ?? email });
      }
      throw e;
    }
  }
  async function perform(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not complete verification.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value && !busy) onClose();
      }}
    >
      <DialogContent>
        <span className="icon-tile mb-5 size-12 rounded-2xl">
          <ShieldCheck size={22} />
        </span>
        <DialogTitle className="pr-8 font-display text-[26px] font-extrabold leading-tight tracking-[-.022em]">
          Confirm your email to start.
        </DialogTitle>
        <DialogDescription className="mt-3 text-[14px] leading-6 text-muted-foreground">
          We’ll scan{" "}
          <strong className="break-all rounded-md bg-lime px-1 font-semibold text-lime-foreground">
            {domain}
          </strong>{" "}
          as soon as you enter the code we email you. No account or password
          needed.
        </DialogDescription>
        {status?.verified && !challenge && !useDifferentEmail ? (
          <div className="mt-5 space-y-4">
            <p className="rounded-2xl bg-success-soft px-4 py-3 text-[14px] font-medium leading-6 text-success">
              {status.development_access ? "Development access" : "Verified"} as{" "}
              {status.email_hint}.
            </p>
            <Button onClick={onVerified} size="lg" className="w-full">
              Continue to scan <ArrowRight size={14} />
            </Button>
            <button
              type="button"
              className="text-[13px] text-muted-foreground underline underline-offset-4"
              onClick={() => setUseDifferentEmail(true)}
            >
              Use another email
            </button>
          </div>
        ) : challenge ? (
          <form
            className="mt-5 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              e.stopPropagation();
              void perform(async () => {
                if (!challenge.challenge_id) return;
                await api.verifyCode(challenge.challenge_id, code);
                onVerified();
              });
            }}
          >
            <p className="text-[14px] leading-6 text-muted-foreground">
              {challenge.challenge_id
                ? "We sent a six-digit code to "
                : "No email was sent to "}
              <strong className="text-foreground">
                {challenge.email_hint}
              </strong>
              {challenge.challenge_id
                ? ". It expires in 10 minutes. Never share the code."
                : ". Configure email delivery and retry, or use the development skip below."}
            </p>
            <label className="block text-[14px] font-semibold">
              Verification code
              <input
                autoFocus
                className="field mt-2 min-h-14 text-center font-mono text-2xl font-semibold tracking-[.4em]"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                required
                disabled={busy}
              />
            </label>
            <Button
              size="lg"
              disabled={busy || !challenge.challenge_id || code.length !== 6}
              className="w-full"
            >
              {busy ? (
                <LoaderCircle size={14} className="animate-spin" />
              ) : (
                <ShieldCheck size={14} />
              )}{" "}
              Verify and scan
            </Button>
            {status?.development_skip_available && (
              <Button
                type="button"
                variant="outline"
                className="w-full"
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    await api.skipVerification(
                      website,
                      selectedCandidate ? undefined : email,
                      selectedCandidate,
                    );
                    onVerified();
                  })
                }
              >
                Skip verification (development)
              </Button>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setChallenge(null);
                setCode("");
                setError("");
              }}
              className="text-[13px] text-muted-foreground underline underline-offset-4"
            >
              Use a different email or request another code
            </button>
          </form>
        ) : (
          <div className="mt-5 space-y-5">
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                e.stopPropagation();
                void perform(async () => {
                  await requestEmail();
                });
              }}
            >
              <label className="block text-[14px] font-semibold">
                Your email
                <input
                  className="field mt-2"
                  type="email"
                  autoComplete="email"
                  placeholder={status?.development_email ?? "you@example.com"}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={busy}
                  maxLength={254}
                />
              </label>
              <p className="text-[12px] leading-5 text-muted-foreground">
                {status?.development_email ? (
                  <>
                    Local development accepts any email so you can test code
                    delivery. You can optionally skip verification at the next
                    step. Payment is a separate step.
                  </>
                ) : (
                  <>
                    We’ll email you a 6-digit code. Any address you can receive
                    works; it doesn’t need to match {domain}.
                  </>
                )}
              </p>
              <Button disabled={busy} size="lg" className="w-full">
                {busy ? (
                  <LoaderCircle size={14} className="animate-spin" />
                ) : (
                  <Mail size={14} />
                )}{" "}
                Send verification code
              </Button>
            </form>
          </div>
        )}
        {error && (
          <div className="mt-4">
            <InlineError>{error}</InlineError>
          </div>
        )}
        <p className="mt-6 border-t pt-4 text-[12px] leading-5 text-muted-foreground">
          We use your email for verification and report access.{" "}
          <Link href="/privacy" className="underline underline-offset-4">
            Privacy Policy
          </Link>{" "}
          ·{" "}
          <Link href="/terms" className="underline underline-offset-4">
            Terms
          </Link>
        </p>
      </DialogContent>
    </Dialog>
  );
}
