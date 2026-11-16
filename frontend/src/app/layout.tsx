import type { Metadata } from "next";
import "./globals.css";
import "./product-theme.css";
import {
  Funnel_Display,
  Instrument_Sans,
  JetBrains_Mono,
} from "next/font/google";

// Self-hosted at build time by next/font (SIL Open Font License). One family for
// headings and text keeps the product calm; mono is for code and data. Funnel
// Display is used once: the rotating agent name in the landing headline.
const text = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-text",
  display: "swap",
});
const code = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-code",
  display: "swap",
});
const agent = Funnel_Display({
  subsets: ["latin"],
  variable: "--font-agent",
  display: "swap",
});
export const metadata: Metadata = {
  title: "Aglanetic — Can AI agents use your website?",
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
      className={`${text.variable} ${code.variable} ${agent.variable}`}
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
