"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Bot,
  ChevronRight,
  FolderKanban,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { LEGAL_DETAILS } from "@/lib/legal";
import { Brand, ThemeToggle } from "./product-ui";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./ui/dialog";
const navigation = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/scans", label: "Scans", icon: ScanLine },
  { href: "/agent-tests", label: "Agent Tests", icon: Bot },
];
export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const [collapsed, setCollapsed] = useState(false);
  const current =
    navigation.find((n) => path.startsWith(n.href)) ?? navigation[0];
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const close = () => {
      if (media.matches) setOpen(false);
    };
    media.addEventListener("change", close);
    return () => media.removeEventListener("change", close);
  }, []);
  const renderSidebar = (compact: boolean) => (
    <>
      <div className="flex h-[78px] items-center justify-between border-b px-5">
        <Brand compact={compact} />
      </div>
      <div className="p-4">
        <div
          className={cn(
            "mb-7 flex items-center gap-3 rounded-lg border bg-background p-3",
            compact && "justify-center px-0",
          )}
        >
          <span className="grid size-7 shrink-0 place-items-center rounded-md border bg-card text-[12px] font-semibold">
            AR
          </span>
          {!compact && (
            <div>
              <p className="text-[13px] font-medium">Your workspace</p>
              <p className="mt-0.5 text-[12px] text-muted-foreground">
                Local workspace
              </p>
            </div>
          )}
        </div>
        {!compact && <p className="eyebrow mb-3 px-3 text-[12px]">Workspace</p>}
        <nav aria-label="Workspace" className="space-y-1">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              title={compact ? label : undefined}
              aria-current={path.startsWith(href) ? "page" : undefined}
              onClick={() => setOpen(false)}
              className={cn(
                "flex min-h-10 items-center gap-3 rounded-lg px-3 text-[14px]",
                path.startsWith(href)
                  ? "bg-accent-soft font-medium text-signal"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
                compact && "justify-center px-0",
              )}
            >
              <Icon size={17} strokeWidth={1.6} />
              {!compact && label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="mt-auto p-4">
        {!compact && (
          <div className="mb-4 rounded-xl border bg-background p-4">
            <span className="mb-3 inline-flex items-center gap-1.5 text-[12px] font-medium text-signal">
              <span className="size-1.5 rounded-full bg-signal" />
              AI agent tests · Christmas 2026
            </span>
            <p className="text-[13px] leading-5 text-muted-foreground">
              Coming soon. Start with static checks and evidence-backed fixes
              today.
            </p>
          </div>
        )}
        <Link
          href="/docs"
          className={cn(
            "flex items-center gap-3 rounded-lg p-3 text-xs text-muted-foreground hover:bg-muted",
            compact && "justify-center",
          )}
          title="Documentation"
        >
          <BookOpen size={16} />
          {!compact && (
            <>
              Documentation
              <ChevronRight className="ml-auto" size={13} />
            </>
          )}
        </Link>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="mt-2 hidden w-full items-center justify-center rounded-lg border py-2.5 text-muted-foreground hover:bg-muted lg:flex"
          aria-label={compact ? "Expand sidebar" : "Collapse sidebar"}
        >
          <PanelLeftClose size={15} className={compact ? "rotate-180" : ""} />
        </button>
        {!compact && (
          <div className="mt-4 border-t px-2 pt-4 text-[12px] text-muted-foreground">
            <nav aria-label="Legal" className="flex flex-wrap gap-x-4 gap-y-2">
              <Link
                href="/privacy"
                onClick={() => setOpen(false)}
                className="hover:text-foreground"
              >
                Privacy Policy
              </Link>
              <Link
                href="/terms"
                onClick={() => setOpen(false)}
                className="hover:text-foreground"
              >
                Terms & Conditions
              </Link>
            </nav>
            <p className="mt-3">© {LEGAL_DETAILS.copyrightYear} AgentLane.</p>
          </div>
        )}
      </div>
    </>
  );
  return (
    <div
      className={cn(
        "workspace-shell min-h-screen transition-[padding]",
        collapsed ? "lg:pl-[84px]" : "lg:pl-[232px]",
      )}
    >
      <a
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-[100] rounded bg-card px-4 py-3 text-sm focus:not-sr-only"
      >
        Skip to content
      </a>
      <aside
        className={cn(
          "workspace-sidebar fixed inset-y-0 left-0 z-40 hidden flex-col border-r bg-card lg:flex",
          collapsed ? "w-[84px]" : "w-[232px]",
        )}
      >
        {renderSidebar(collapsed)}
      </aside>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            menuButton.current?.focus();
          }}
          className="left-0 top-0 flex h-dvh w-[280px] max-w-[85vw] translate-x-0 translate-y-0 flex-col gap-0 rounded-none border-0 border-r p-0"
        >
          <DialogTitle className="sr-only">Workspace navigation</DialogTitle>
          <DialogDescription className="sr-only">
            Navigate between your overview, projects, scans, and agent tests.
          </DialogDescription>
          {renderSidebar(false)}
        </DialogContent>
      </Dialog>
      <header className="sticky top-0 z-30 flex h-[65px] items-center justify-between gap-3 border-b bg-background/95 px-5 backdrop-blur-sm sm:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <button
            className="grid size-9 place-items-center rounded-lg border bg-card lg:hidden"
            ref={menuButton}
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Menu size={18} />
          </button>
          <div className="flex min-w-0 items-center gap-2 text-[13px] text-muted-foreground">
            <span className="hidden sm:inline">Workspace</span>
            <ChevronRight className="hidden sm:block" size={12} />
            <Link href={current.href} className="font-medium text-foreground">
              {current.label}
            </Link>
            {path.split("/").filter(Boolean).length > 1 && (
              <>
                <ChevronRight size={12} />
                <span className="truncate">
                  {path.startsWith("/agent-tests")
                    ? "Execution"
                    : path.startsWith("/projects")
                      ? "Project details"
                      : "Scan results"}
                </span>
              </>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="hidden items-center gap-1.5 text-[12px] text-muted-foreground sm:flex">
            <ShieldCheck size={13} />
            Read-only testing
          </span>
          <ThemeToggle />
        </div>
      </header>
      <main
        id="main-content"
        className="mx-auto max-w-[1480px] px-5 py-8 sm:px-8 lg:px-9 lg:py-9"
      >
        {children}
      </main>
    </div>
  );
}
