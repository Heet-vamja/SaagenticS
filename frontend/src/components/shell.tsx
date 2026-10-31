"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Boxes,
  CircleHelp,
  LayoutDashboard,
  ScanLine,
  Sparkles,
} from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: Boxes },
  { href: "/scans", label: "Scans", icon: ScanLine },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen lg:pl-[244px]">
      <aside className="flex flex-col bg-[#202723] px-5 py-6 text-[#edf1e9] lg:fixed lg:inset-y-0 lg:left-0 lg:w-[244px]">
        <Link
          href="/"
          className="mb-7 flex items-center gap-2.5 px-2 text-lg font-semibold tracking-tight"
        >
          <span className="grid size-8 place-items-center rounded-lg bg-[#e8f1d9] text-[#283b24]">
            <Activity size={21} />
          </span>
          AgentReadiness<span className="text-primary">.</span>
        </Link>
        <div className="mb-8 hidden items-center gap-3 rounded-lg border border-white/10 p-3 lg:flex">
          <span className="grid size-8 place-items-center rounded-md bg-white/10 text-xs font-medium">
            AR
          </span>
          <div>
            <p className="text-xs font-medium">Your workspace</p>
            <p className="mt-1 text-[11px] text-white/45">
              Development preview
            </p>
          </div>
        </div>
        <p className="mb-3 hidden px-3 text-[10px] font-medium uppercase tracking-[.16em] text-white/35 lg:block">
          Workspace
        </p>
        <nav className="flex gap-1 lg:flex-col">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-3 text-sm transition-colors",
                (href === "/" ? pathname === href : pathname.startsWith(href))
                  ? "bg-[#364039] text-[#e6f3d4]"
                  : "text-white/55 hover:bg-white/5 hover:text-white",
              )}
            >
              <Icon size={18} strokeWidth={1.7} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto hidden pt-16 lg:block">
          <div className="rounded-xl border border-white/10 bg-white/[.025] p-4">
            <Sparkles size={19} className="mb-3 text-[#c8dcae]" />
            <p className="text-sm font-medium">Built for what’s next.</p>
            <p className="mt-2 text-xs leading-5 text-white/45">
              A clearer view of how AI agents experience your website.
            </p>
          </div>
          <a
            href="http://localhost:8000/docs"
            className="mt-5 flex items-center justify-between px-2 text-xs text-white/50"
          >
            <span className="flex items-center gap-2">
              <BookOpen size={15} />
              Local API documentation
            </span>
            <ArrowUpRight size={14} />
          </a>
        </div>
      </aside>
      <header className="flex h-[76px] items-center justify-between border-b border-border/70 bg-background px-6 lg:px-10">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          Workspace <span className="mx-1 text-border">/</span>
          <span className="font-medium text-foreground">
            {pathname === "/"
              ? "Overview"
              : pathname.startsWith("/projects")
                ? "Projects"
                : "Scans"}
          </span>
        </div>
        <span className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-[11px] text-muted-foreground">
          <span className="size-1.5 rounded-full bg-amber-500" />
          Foundation preview
          <CircleHelp size={13} />
        </span>
      </header>
      <main className="mx-auto max-w-[1440px] px-5 py-9 sm:px-8 lg:px-10">
        {children}
      </main>
    </div>
  );
}
