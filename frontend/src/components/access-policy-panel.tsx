import { ChevronDown, ShieldCheck } from "lucide-react";
import type { FreeAccessPolicy } from "@/lib/types";

/** A policy declaration is not a provider execution or a search-visibility test. */
export function AccessPolicyPanel({
  policies,
  inspectionLimited = false,
}: {
  policies?: FreeAccessPolicy[];
  inspectionLimited?: boolean;
}) {
  if (!policies?.length) return null;
  const scanner = policies.filter((row) => row.kind === "SCANNER");
  const incomplete =
    inspectionLimited || scanner.some((row) => row.policy !== "ALLOWED");
  return (
    <details className="group/access surface mb-6 overflow-hidden">
      <summary className="flex cursor-pointer list-none items-center gap-4 p-5 text-xs focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
        <span
          className={`grid size-10 shrink-0 place-items-center rounded-xl ${incomplete ? "bg-warning-soft text-warning" : "bg-accent-soft text-signal"}`}
        >
          <ShieldCheck size={19} />
        </span>
        <span className="min-w-0 flex-1">
          <strong className="block font-display text-[16px] font-bold tracking-[-.02em]">
            Our scanner & AI-bot policies
          </strong>
          <span className="mt-1 block text-[13px] leading-5 text-muted-foreground">
            {incomplete
              ? "Our inspection was limited. This does not establish that ChatGPT or other providers are blocked."
              : "Robots permissions are declared policies, not verified provider access or AI-search visibility."}
          </span>
        </span>
        <ChevronDown
          size={14}
          className="shrink-0 text-muted-foreground transition-transform group-open/access:rotate-180"
        />
      </summary>
      <div className="border-t px-5 pb-5">
        <p className="py-4 text-[14px] leading-6 text-muted-foreground">
          We use our own crawler identity and do not impersonate other bots. The
          rows below describe robots.txt for the sampled path only. “Allowed”
          does not prove that a provider fetched the page, recommended this
          website, or completed a task. An unknown policy was not assessed.
        </p>
        <div className="overflow-x-auto rounded-2xl border">
          <table className="w-full text-left text-[13px]">
            <caption className="sr-only">
              Scanner-specific and declared AI-bot permissions, without verified
              task access
            </caption>
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3 font-medium">Identity</th>
                <th className="px-4 py-3 font-medium">Robots policy</th>
                <th className="px-4 py-3 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((row, index) => (
                <tr
                  key={`${row.kind}-${row.user_agent}-${row.sampled_url}-${index}`}
                  className="border-t"
                >
                  <td className="px-4 py-3.5">
                    <span className="block font-mono text-[12px] font-medium">
                      {row.user_agent}
                    </span>
                    <span className="mt-1 block text-[12px] text-muted-foreground">
                      {row.kind === "SCANNER"
                        ? "Our scanner"
                        : "Named AI bot · access not verified"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3.5">
                    <span
                      className={`rounded-full px-2.5 py-1 text-[12px] font-bold ${row.policy === "ALLOWED" ? "bg-success-soft text-success" : row.policy === "DISALLOWED" ? "bg-warning-soft text-warning" : "bg-muted text-muted-foreground"}`}
                    >
                      {row.policy === "ALLOWED"
                        ? "Allowed by policy"
                        : row.policy === "DISALLOWED"
                          ? "Disallowed by policy"
                          : "Not assessed"}
                    </span>
                  </td>
                  <td className="min-w-36 px-4 py-3.5">
                    <a
                      href={row.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-all text-[12px] text-muted-foreground underline underline-offset-4"
                    >
                      robots.txt
                      {row.http_status !== null
                        ? ` · HTTP ${row.http_status}`
                        : ""}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {incomplete && (
          <p className="mt-4 rounded-2xl bg-warning-soft p-4 text-[13px] leading-6 text-foreground">
            Website owner? Review the recorded response and allowlist our
            crawler (AgentReadinessBot) or its deployment IP if appropriate.
            Preserve security protections. We do not bypass access restrictions;
            an inaccessible page is not evidence that every AI agent is blocked.
          </p>
        )}
      </div>
    </details>
  );
}
