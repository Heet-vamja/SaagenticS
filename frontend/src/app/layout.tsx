import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "AgentReadiness — Your workspace",
  description:
    "A foundation for understanding how AI agents experience your website.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
