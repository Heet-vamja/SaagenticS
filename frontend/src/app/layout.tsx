import type { Metadata } from "next";
import "./globals.css";
import "./product-theme.css";
import { Funnel_Display, Geist, Geist_Mono } from "next/font/google";

// Self-hosted at build time by next/font (SIL Open Font License): Funnel Display
// for headings, Geist for text, Geist Mono for code and data.
const display = Funnel_Display({
  subsets: ["latin"],
  variable: "--font-heading",
  display: "swap",
});
const text = Geist({
  subsets: ["latin"],
  variable: "--font-text",
  display: "swap",
});
const code = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-code",
  display: "swap",
});
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
      className={`${display.variable} ${text.variable} ${code.variable}`}
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
