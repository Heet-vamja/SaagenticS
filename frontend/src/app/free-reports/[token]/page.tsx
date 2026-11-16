import type { Metadata } from "next";
import { FreeScanReport } from "@/components/free-scan-report";

export const metadata: Metadata = {
  title: "Your free readiness report | Aglanetic",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function FreeReportPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <FreeScanReport key={token} token={token} />;
}
