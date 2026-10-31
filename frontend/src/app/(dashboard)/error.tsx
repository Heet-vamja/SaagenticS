"use client";
import { ErrorState } from "@/components/states";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <ErrorState message="We couldn’t load this page." retry={reset} />;
}
