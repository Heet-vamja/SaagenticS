import { ScanDetail } from "@/components/scan-detail";
export default async function ScanPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ScanDetail id={id} />;
}
