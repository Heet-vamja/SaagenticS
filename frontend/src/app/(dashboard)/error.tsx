"use client";
import { ErrorState } from "@/components/states";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main-content" className="marketing-wrap max-w-3xl py-20 sm:py-28">
      <ErrorState message="We couldn’t load this page." retry={reset} />
    </main>
  );
}
