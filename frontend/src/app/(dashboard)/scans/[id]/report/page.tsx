import { ReportView } from "@/components/static-report";
export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReportView scanId={id} />;
}
