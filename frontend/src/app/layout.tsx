import type { Metadata } from "next";
import "./globals.css";
import "./product-theme.css";
import localFont from "next/font/local";
const funnel = localFont({
  src: "./fonts/FunnelDisplay-Variable.ttf",
  variable: "--font-heading",
  display: "swap",
  weight: "300 800",
});
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
export const metadata: Metadata = {
  title: "AgentLane — Can AI agents use your website?",
  description:
    "Find technical barriers for AI agents. Verify your email, get a static readiness score, and unlock the full report for $19.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      suppressHydrationWarning
      className={`${funnel.variable} ${GeistSans.variable} ${GeistMono.variable}`}
    >
      <head>
        <script
          id="theme-init"
          dangerouslySetInnerHTML={{
            __html: `(function(){var t;try{t=localStorage.getItem('ar-theme')}catch(e){}document.documentElement.dataset.theme=t==='dark'||t==='light'?t:window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'})()`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
