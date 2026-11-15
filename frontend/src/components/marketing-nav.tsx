"use client";
import Link from "next/link";
import { Menu, X, ArrowRight, ArrowUpRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Brand, ThemeToggle } from "./product-ui";
import { Button } from "./ui/button";
import { LEGAL_DETAILS } from "@/lib/legal";

const NAV_LINKS = [
  ["How it works", "/#how-it-works"],
  ["Pricing", "/#pricing"],
  ["Agent lane", "/#agent-lane"],
  ["Docs", "/docs"],
] as const;

export function MarketingNav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header
      className={`marketing-header nav-glass sticky top-0 z-40 border-b border-border/60 transition-shadow duration-300 ${scrolled ? "shadow-card" : ""}`}
    >
      <div className="marketing-wrap flex h-16 items-center justify-between gap-4">
        <Brand />
        <nav
          aria-label="Main navigation"
          className="hidden items-center gap-1 text-[14px] font-medium text-muted-foreground lg:flex"
        >
          {NAV_LINKS.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              className="rounded-full px-3.5 py-2 hover:bg-muted hover:text-foreground"
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <Button asChild size="sm" className="hidden sm:inline-flex">
            <Link href="/#scan">
              Scan your site
              <ArrowRight size={14} />
            </Link>
          </Button>
          <button
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="marketing-mobile-nav"
            className="grid size-10 place-items-center rounded-full hover:bg-muted lg:hidden"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </div>
      {open && (
        <nav
          id="marketing-mobile-nav"
          aria-label="Mobile navigation"
          className="marketing-wrap flex flex-col gap-1 border-t border-border/60 py-3 lg:hidden"
        >
          {[...NAV_LINKS, ["Scan your site", "/#scan"] as const].map(
            ([label, href]) => (
              <Link
                key={label}
                href={href}
                onClick={() => setOpen(false)}
                className="rounded-2xl px-4 py-3 font-display text-[18px] font-bold tracking-[-.02em] hover:bg-muted"
              >
                {label}
              </Link>
            ),
          )}
        </nav>
      )}
    </header>
  );
}

const FOOTER_GROUPS: {
  title: string;
  links: { label: string; href: string; external?: boolean }[];
}[] = [
  {
    title: "Product",
    links: [
      { label: "How it works", href: "/#how-it-works" },
      { label: "Pricing", href: "/#pricing" },
      { label: "Agent lane (in development)", href: "/#agent-lane" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Documentation", href: "/docs" },
      {
        label: "AgentReady standard",
        href: "https://www.agentready.org/",
        external: true,
      },
      {
        label: "GitHub",
        href: "https://github.com/Heet-vamja/SaagenticS",
        external: true,
      },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms & Conditions", href: "/terms" },
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="border-t bg-muted/60">
      <div className="marketing-wrap grid gap-10 py-14 md:grid-cols-[1.4fr_repeat(3,1fr)] md:py-16">
        <div className="max-w-xs">
          <Brand />
          <p className="mt-4 text-[14px] leading-6 text-muted-foreground">
            A better web for the agents using it. Find what blocks AI agents,
            fix it, and check that it worked.
          </p>
        </div>
        {FOOTER_GROUPS.map((group) => (
          <nav key={group.title} aria-label={group.title}>
            <h2 className="text-[14px] font-medium text-foreground">
              {group.title}
            </h2>
            <ul className="mt-4 space-y-3 text-[14px]">
              {group.links.map((link) => (
                <li key={link.label}>
                  {link.external ? (
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                      {link.label}
                      <ArrowUpRight size={13} aria-hidden="true" />
                    </a>
                  ) : (
                    <Link
                      href={link.href}
                      className="text-muted-foreground transition-colors duration-200 hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t">
        <div className="marketing-wrap flex flex-wrap items-center justify-between gap-3 py-6 text-[13px] text-muted-foreground">
          <p>© {LEGAL_DETAILS.copyrightYear} AgentLane. All rights reserved.</p>
          <p>Read-only checks. No changes are made to your website.</p>
        </div>
      </div>
    </footer>
  );
}
