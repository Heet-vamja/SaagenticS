import { ArrowRight, LoaderCircle, Telescope } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./ui/button";

export function LoadingState() {
  return (
    <div
      role="status"
      className="flex min-h-64 items-center justify-center gap-3 text-sm text-muted-foreground"
    >
      <LoaderCircle className="animate-spin" size={18} />
      Loading your workspace…
    </div>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 p-6"
    >
      <p className="mb-3 text-sm text-red-800">{message}</p>
      <Button variant="outline" onClick={retry}>
        Try again
      </Button>
    </div>
  );
}
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-5 py-16 text-center">
      <div className="mb-5 grid size-14 place-items-center rounded-2xl border bg-background text-primary">
        <Telescope size={25} strokeWidth={1.5} />
      </div>
      <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      <p className="mb-6 mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
      {action}
    </div>
  );
}
export function ComingSoon() {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      Coming next <ArrowRight size={12} />
    </span>
  );
}
