"use client";
import Link from "next/link";
import { Menu, X, ArrowUpRight } from "lucide-react";
import { useState } from "react";
import { Brand, ThemeToggle } from "./product-ui";
import { Button } from "./ui/button";
export function MarketingNav({ dark = false }: { dark?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <header
      className={`marketing-header sticky top-0 z-40 ${dark ? "marketing-header-dark" : "border-b border-border/70 bg-background/95 backdrop-blur-sm"}`}
    >
      <div className="marketing-wrap flex h-[76px] items-center justify-between gap-4">
        <Brand />
        <nav
          aria-label="Main navigation"
          className="hidden items-center gap-7 text-xs text-muted-foreground lg:flex"
        >
          <Link href="/#product" className="hover:text-foreground">
            Product
          </Link>
          <Link href="/#how-it-works" className="hover:text-foreground">
            How it works
          </Link>
          <Link href="/#features" className="hover:text-foreground">
            Features
          </Link>
          <Link href="/docs" className="hover:text-foreground">
            Documentation
          </Link>
        </nav>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            className="mr-3 hidden text-xs font-medium text-muted-foreground sm:block"
          >
            Dashboard
          </Link>
          <ThemeToggle />
          <Button asChild className="hidden sm:inline-flex">
            <Link href="/#scan">
              Scan your website
              <ArrowUpRight size={13} />
            </Link>
          </Button>
          <button
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="grid size-10 place-items-center rounded-lg border lg:hidden"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>
      {open && (
        <nav
          aria-label="Mobile navigation"
          className="marketing-wrap flex flex-col gap-1 border-t py-3 lg:hidden"
        >
          {[
            ["Product", "/#product"],
            ["How it works", "/#how-it-works"],
            ["Features", "/#features"],
            ["Documentation", "/docs"],
            ["Dashboard", "/dashboard"],
            ["Scan your website", "/#scan"],
          ].map(([label, href]) => (
            <Link
              key={label}
              href={href}
              onClick={() => setOpen(false)}
              className="rounded-lg px-3 py-3 text-sm hover:bg-muted"
            >
              {label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
export function MarketingFooter() {
  return (
    <footer className="border-t py-9">
      <div className="marketing-wrap flex flex-wrap items-center justify-between gap-6">
        <div>
          <Brand />
          <p className="mt-3 text-[11px] text-muted-foreground">
            A better web for the agents using it.
          </p>
        </div>
        <nav
          aria-label="Footer"
          className="flex flex-wrap gap-6 text-[11px] text-muted-foreground"
        >
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/docs">Documentation</Link>
          <Link href="/docs#data">Privacy & data handling</Link>
          <a
            href="https://github.com/Heet-vamja/SaagenticS"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
        </nav>
      </div>
    </footer>
  );
}
