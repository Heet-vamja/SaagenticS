"use client";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  ChevronRight,
  Copy,
  Globe2,
  Moon,
  Sun,
} from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** AgentLane mark: a lime tile with an ink lane vanishing into an "A". */
export function LogoMark({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
      className={cn("brand-symbol shrink-0", className)}
    >
      {/* Split lane: one path forks. The straight lane is the site as people see
          it; the branching lane is the agent lane. Colors follow the theme. */}
      <rect width="64" height="64" rx="18" fill="var(--logo-tile)" />
      <path
        d="M25 50c0-13 14-14 14-26V14"
        fill="none"
        stroke="var(--logo-agent)"
        strokeWidth={size < 24 ? 10 : 8}
        strokeLinecap="round"
      />
      <path
        d="M25 50V14"
        fill="none"
        stroke="var(--logo-lane)"
        strokeWidth={size < 24 ? 10 : 8}
        strokeLinecap="round"
      />
    </svg>
  );
}
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      href="/"
      aria-label="AgentLane home"
      className="inline-flex shrink-0 items-center gap-2.5"
    >
      <LogoMark />
      {!compact && (
        <span className="font-display text-[19px] font-extrabold tracking-[-.022em]">
          AgentLane
        </span>
      )}
    </Link>
  );
}
export function ThemeToggle() {
  const theme = useSyncExternalStore(
    (cb) => {
      window.addEventListener("ar-theme", cb);
      return () => window.removeEventListener("ar-theme", cb);
    },
    () => document.documentElement.dataset.theme ?? "light",
    () => "light",
  );
  useEffect(() => {
    try {
      const saved = localStorage.getItem("ar-theme");
      document.documentElement.dataset.theme =
        saved === "dark" || saved === "light"
          ? saved
          : (document.documentElement.dataset.theme ??
            (window.matchMedia("(prefers-color-scheme: dark)").matches
              ? "dark"
              : "light"));
      window.dispatchEvent(new Event("ar-theme"));
    } catch {}
  }, []);
  return (
    <button
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      aria-pressed={theme === "dark"}
      className="grid size-10 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
      onClick={() => {
        const next = theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        try {
          localStorage.setItem("ar-theme", next);
        } catch {}
        window.dispatchEvent(new Event("ar-theme"));
      }}
    >
      {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}
export function Status({
  value,
  timeout = false,
}: {
  value: string;
  timeout?: boolean;
}) {
  const label = timeout
    ? "Timed out"
    : ({
        COMPLETED: "Completed",
        FAILED: "Failed",
        RUNNING: "Running",
        PENDING: "Pending",
        PASSED: "Passed",
      }[value] ?? value);
  const tone = value === "PASSED" ? "completed" : value.toLowerCase();
  return (
    <span className={cn("status-badge", `status-${tone}`)}>
      <span
        className={cn(
          "size-1.5 rounded-full bg-current",
          value === "RUNNING" && "animate-pulse",
        )}
      />
      {label}
    </span>
  );
}
export function DomainIcon({ className = "" }: { className?: string }) {
  return (
    <span
      className={cn(
        "grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-signal",
        className,
      )}
    >
      <Globe2 size={18} strokeWidth={1.5} />
    </span>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
  back,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  back?: { href: string; label: string };
}) {
  return (
    <div className="page-heading mb-8">
      {back && (
        <Link
          href={back.href}
          className="mb-5 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft size={13} />
          {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
          <h1 className="font-display break-words text-[28px] font-extrabold leading-tight tracking-[-.025em] sm:text-[38px]">
            {title}
          </h1>
          {description && (
            <p className="mt-3 max-w-2xl text-[16px] leading-7 text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {action && (
          <div className="flex shrink-0 items-center gap-2 pt-1">{action}</div>
        )}
      </div>
    </div>
  );
}
export function Metric({
  label,
  value,
  icon: Icon,
  detail,
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  detail?: string;
}) {
  return (
    <div className="metric-card surface p-5">
      <div className="flex items-center justify-between gap-2 text-[13px] text-muted-foreground">
        <span>{label}</span>
        <Icon size={15} strokeWidth={1.6} />
      </div>
      <p className="my-3 font-display text-[34px] font-extrabold leading-none tracking-[-.025em] tabular-nums">
        {value}
      </p>
      {detail && <p className="text-[12px] text-muted-foreground">{detail}</p>}
    </div>
  );
}
export function SectionHeader({
  title,
  description,
  count,
  action,
}: {
  title: string;
  description?: string;
  count?: number;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="section-title">{title}</h2>
          {count !== undefined && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[12px] font-semibold text-muted-foreground">
              {count}
            </span>
          )}
        </div>
        {description && (
          <p className="mt-1 text-[13px] leading-5 text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}
export function TextLink({
  href,
  children,
  external = false,
}: {
  href: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  return (
    <Link
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
      className="inline-flex items-center gap-1 text-xs font-semibold text-signal hover:underline hover:underline-offset-4"
    >
      {children}
      {external ? <ArrowUpRight size={13} /> : <ChevronRight size={13} />}
    </Link>
  );
}
export function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(t);
  }, [copied]);
  return (
    <button
      aria-label={copied ? "Copied" : "Copy ID"}
      className="rounded-full p-1.5 text-muted-foreground hover:bg-muted"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
    </button>
  );
}
export function VerificationNotice() {
  return (
    <div className="flex items-start gap-2 text-[12px] leading-5 text-muted-foreground">
      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warning" />
      <span>
        <strong className="font-medium text-foreground">
          Not independently verified.
        </strong>{" "}
        Independent evaluation is not enabled.
      </span>
    </div>
  );
}
export function formatDate(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "Not started";
}
export function domainOf(url: string) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
export function duration(value: number | null) {
  return value === null
    ? "—"
    : value < 60
      ? `${value.toFixed(1)}s`
      : `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
}
