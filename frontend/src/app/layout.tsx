import type { Metadata } from "next";
import "./globals.css";
import localFont from "next/font/local";
const manrope = localFont({
  src: "./fonts/Manrope-Variable.ttf",
  variable: "--font-manrope",
  display: "swap",
  weight: "200 800",
});
const spaceGrotesk = localFont({
  src: "./fonts/SpaceGrotesk-Variable.ttf",
  variable: "--font-space-grotesk",
  display: "swap",
  weight: "300 700",
});
import { GeistMono } from "geist/font/mono";
export const metadata: Metadata = {
  title: "AgentReadiness — Can AI agents use your website?",
  description:
    "Test how real AI agents discover, navigate, and interact with your website.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${manrope.variable} ${spaceGrotesk.variable} ${GeistMono.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
