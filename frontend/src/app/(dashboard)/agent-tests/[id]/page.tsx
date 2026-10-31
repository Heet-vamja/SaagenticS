import { AgentDetail } from "@/components/agent-detail";
export default async function AgentTestPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AgentDetail key={id} id={id} />;
}
