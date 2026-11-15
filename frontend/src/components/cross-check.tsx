"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight, Check, Copy } from "lucide-react";

/** Commands use only the parsed hostname, so they never carry paths, queries or tokens. */
function hostOf(website: string) {
  try {
    const host = new URL(website).hostname;
    return /^[a-z0-9.-]+$/i.test(host) ? host : null;
  } catch {
    return null;
  }
}

function requests(host: string) {
  const origin = `https://${host}`;
  return [
    {
      title: "Your robots.txt",
      command: `curl -sS ${origin}/robots.txt`,
      look: "Rules under User-agent: * apply to every agent. A Disallow: / there, or for named AI crawlers, keeps them out.",
    },
    {
      title: "What an agent reads before JavaScript runs",
      command: `curl -sSL ${origin}/ | sed -e 's/<[^>]*>/ /g' | tr -s ' \\n' | head -c 1500`,
      look: "If your product, pricing or docs links are missing here, many agents miss them too.",
    },
    {
      title: "A page that does not exist",
      command: `curl -sS -o /dev/null -w "%{http_code}\\n" ${origin}/agentlane-check-404`,
      look: "Should print 404. A 200 means agents can’t tell a missing page from a real one.",
    },
    {
      title: "Your sitemap",
      command: `curl -sSI ${origin}/sitemap.xml`,
      look: "A 200 with an XML content type lets agents list your pages without guessing.",
    },
    {
      title: "Optional agent files",
      command: `curl -sS ${origin}/llms.txt; curl -sS ${origin}/.well-known/ai-catalog.json`,
      look: "Both are optional. If they exist, they should list real pages and resources.",
    },
  ];
}

function CopyCommand({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(timer);
  }, [copied]);
  return (
    <button
      type="button"
      aria-label={copied ? "Command copied" : "Copy command"}
      className="grid size-8 shrink-0 place-items-center rounded-full text-[#c9c6d3] hover:bg-white/10 hover:text-white"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

function Command({ value }: { value: string }) {
  return (
    <div className="mt-3 flex items-start gap-2 rounded-xl border border-white/10 bg-[#0e1013] py-2 pr-2 pl-3.5">
      <code className="min-w-0 flex-1 py-1.5 font-mono text-[12.5px] leading-6 break-all whitespace-pre-wrap text-[#f4f4f1]">
        {value}
      </code>
      <CopyCommand value={value} />
    </div>
  );
}

const label =
  "rounded-full bg-muted px-2.5 py-0.5 text-[12px] font-semibold text-muted-foreground";
const link =
  "mt-3 inline-flex items-center gap-1 text-[14px] font-semibold text-primary hover:underline hover:underline-offset-4";

export function CrossCheck({ website }: { website: string }) {
  const host = hostOf(website);
  if (!host) return null;
  return (
    <section
      aria-labelledby="cross-check-title"
      className="surface mt-6 overflow-hidden p-6 sm:p-9"
    >
      <p className="chip">
        <span className="chip-dot" aria-hidden="true" />
        Check our work
      </p>
      <div className="mt-5 grid gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="min-w-0">
          <h2 id="cross-check-title" className="display-md">
            Don’t take our word for it.
          </h2>
          <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted-foreground">
            Every result in this report comes from a public request anyone can
            repeat. Run these from your own terminal to see what we saw. They
            only read public pages.
          </p>
          <ol className="mt-7 space-y-3">
            {requests(host).map((item, index) => (
              <li
                key={item.title}
                className="rounded-2xl border bg-background p-4 sm:p-5"
              >
                <div className="flex items-center gap-3">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft font-mono text-[12px] font-semibold text-signal">
                    {index + 1}
                  </span>
                  <h3 className="text-[16px]">{item.title}</h3>
                </div>
                <Command value={item.command} />
                <p className="mt-2.5 text-[14px] leading-6 text-muted-foreground">
                  {item.look}
                </p>
              </li>
            ))}
          </ol>
        </div>
        <aside aria-labelledby="independent-tools-title" className="min-w-0">
          <h3 id="independent-tools-title" className="text-[19px]">
            Compare with independent tools
          </h3>
          <p className="mt-2 text-[14px] leading-6 text-muted-foreground">
            These projects are not affiliated with AgentLane and do not endorse
            it. Their checks, weights and page samples differ from ours, so
            compare individual findings, not totals.
          </p>
          <ul className="mt-5 space-y-3">
            <li className="rounded-2xl border bg-background p-5">
              <p className="flex flex-wrap items-center gap-2">
                <strong className="font-display text-[17px]">AgentReady</strong>
                <span className={label}>Open standard · MIT</span>
              </p>
              <p className="mt-2 text-[14px] leading-6 text-muted-foreground">
                The public checklist our coverage table maps to. Use it to see
                which requirements we measure and which we leave out.
              </p>
              <a
                href="https://www.agentready.org/"
                target="_blank"
                rel="noopener noreferrer"
                className={link}
              >
                Read the standard <ArrowUpRight size={13} aria-hidden="true" />
              </a>
            </li>
            <li className="rounded-2xl border bg-background p-5">
              <p className="flex flex-wrap items-center gap-2">
                <strong className="font-display text-[17px]">Is Agentic</strong>
                <span className={label}>By Vercel · data from Ora</span>
              </p>
              <p className="mt-2 text-[14px] leading-6 text-muted-foreground">
                A free scanner that follows the same standard. Opening its
                report or running its CLI may create a public report of{" "}
                <span className="mono">{host}</span> on Is Agentic.
              </p>
              <Command value={`npx is-agentic ${host}`} />
              <a
                href={`https://is-agentic.com/scan/${host}`}
                target="_blank"
                rel="noopener noreferrer"
                className={link}
              >
                Open its report for {host}
                <ArrowUpRight size={13} aria-hidden="true" />
              </a>
            </li>
          </ul>
          <div className="mt-3 rounded-2xl bg-accent-soft p-5">
            <h4 className="text-[15px]">If the results differ</h4>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-[14px] leading-6 text-muted-foreground">
              <li>
                We read up to 10 public pages without running a model. Other
                tools may read more pages or run real agents.
              </li>
              <li>Sites change. Compare reports from the same day.</li>
              <li>
                If another tool finds a real problem we missed, fix it too. A
                good fix should hold up in any honest scanner.
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </section>
  );
}
