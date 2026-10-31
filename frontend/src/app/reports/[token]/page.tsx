import type { Metadata } from "next";
import { ReportView } from "@/components/static-report";
export const metadata: Metadata = {
  title: "Shared static readiness report | AgentReadiness",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export default async function SharedReportPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <ReportView token={token} />;
}
