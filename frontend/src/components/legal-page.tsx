import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowUpRight, FileText } from "lucide-react";
import { MarketingFooter, MarketingNav } from "./marketing-nav";
import { LEGAL_DETAILS } from "@/lib/legal";

export type LegalSection = { id: string; title: string; content: ReactNode };

export function LegalPage({
  title,
  description,
  sections,
}: {
  title: string;
  description: string;
  sections: LegalSection[];
}) {
  return (
    <>
      <MarketingNav />
      <main id="main-content" className="legal-page">
        <header className="marketing-wrap pb-10 pt-16 text-center sm:pb-14 sm:pt-24">
          <p className="chip">
            <span className="chip-dot" aria-hidden="true" />
            Trust & transparency
          </p>
          <h1 className="display-lg mx-auto mt-6 max-w-[14ch]">{title}</h1>
          <p className="lede mx-auto mt-5 max-w-2xl">{description}</p>
          <p className="mt-6 font-mono text-[12px] tracking-[.06em] text-muted-foreground">
            Last updated: {LEGAL_DETAILS.updated}
          </p>
        </header>

        <div className="marketing-wrap max-w-[1080px] pb-20">
          <div
            role="note"
            className="mx-auto flex max-w-3xl items-start gap-3 rounded-2xl bg-warning-soft p-4 text-[14px] leading-6 text-foreground sm:p-5"
          >
            <FileText size={18} className="mt-0.5 shrink-0 text-warning" />
            <p>
              <strong className="font-bold text-warning">
                Draft for review.
              </strong>{" "}
              Operator, contact, and jurisdiction details are placeholders.
              These documents need completion and review before public launch.
            </p>
          </div>

          <div className="mt-12 grid items-start gap-10 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-16">
            <nav
              aria-label="On this page"
              className="rounded-3xl border bg-card p-5 lg:sticky lg:top-24 lg:border-0 lg:bg-transparent lg:p-0"
            >
              <p className="eyebrow mb-3">On this page</p>
              <ol className="grid gap-0.5 sm:grid-cols-2 lg:grid-cols-1">
                {sections.map((section, index) => (
                  <li key={section.id}>
                    <a
                      href={`#${section.id}`}
                      className="flex gap-3 rounded-xl px-3 py-2 text-[14px] font-medium leading-5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <span className="font-mono text-[12px] leading-5">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      {section.title}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
            <article className="surface min-w-0 px-6 py-4 sm:px-10 sm:py-6">
              {sections.map((section, index) => (
                <section
                  id={section.id}
                  key={section.id}
                  className="scroll-mt-24 border-b py-8 last:border-0"
                >
                  <div className="flex items-baseline gap-3">
                    <span className="font-mono text-[13px] font-medium text-primary">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <h2 className="text-[22px] font-bold leading-tight tracking-[-.025em] sm:text-[24px]">
                      {section.title}
                    </h2>
                  </div>
                  <div className="legal-copy mt-4 space-y-4 text-[15px] leading-7 text-muted-foreground">
                    {section.content}
                  </div>
                </section>
              ))}
            </article>
          </div>

          <div className="mt-10 flex flex-wrap justify-center gap-3 text-[14px] font-semibold">
            {[
              ["/privacy", "Privacy Policy"],
              ["/terms", "Terms & Conditions"],
              ["/docs", "Product documentation"],
            ].map(([href, label]) => (
              <Link
                key={href}
                href={href}
                className="inline-flex items-center gap-1.5 rounded-full border bg-card px-4 py-2.5 hover:bg-muted"
              >
                {label} <ArrowUpRight size={14} />
              </Link>
            ))}
          </div>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
