import type { Metadata } from "next";
import { OwnerDashboard } from "@/components/owner-dashboard";

export const metadata: Metadata = {
  title: "Dashboard | Aglanetic",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <OwnerDashboard />;
}
