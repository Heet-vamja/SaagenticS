import { AlertCircle, ArrowRight, Telescope } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./ui/button";
export function LoadingState() {
  return (
    <div role="status" aria-label="Loading content" className="space-y-6">
      <span className="sr-only">Loading content…</span>
      <div className="skeleton h-7 w-48" />
      <div className="skeleton h-3 w-72 max-w-full" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[1, 2, 3, 4].map((n) => (
          <div key={n} className="surface space-y-4 p-5">
            <div className="skeleton h-3 w-20" />
            <div className="skeleton h-8 w-12" />
          </div>
        ))}
      </div>
      <div className="surface space-y-6 p-6">
        {[1, 2, 3, 4].map((n) => (
          <div className="skeleton h-4 w-full" key={n} />
        ))}
      </div>
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
      className="surface flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center"
    >
      <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-danger-soft text-danger">
        <AlertCircle size={20} />
      </span>
      <div className="flex-1">
        <h2 className="font-display text-[17px] font-bold">
          Something needs your attention
        </h2>
        <p className="mt-1 break-words text-xs leading-6 text-muted-foreground">
          {message}
        </p>
      </div>
      <Button variant="outline" onClick={retry}>
        Try again <ArrowRight size={13} />
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
    <div className="flex flex-col items-center px-5 py-12 text-center">
      <span className="mb-4 grid size-12 place-items-center rounded-2xl bg-accent-soft text-signal">
        <Telescope size={21} strokeWidth={1.8} />
      </span>
      <h3 className="text-[17px]">{title}</h3>
      <p className="mt-2 max-w-sm text-xs leading-6 text-muted-foreground">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
export function InlineError({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-2xl bg-danger-soft px-4 py-3 text-xs font-medium leading-6 text-danger"
    >
      <AlertCircle className="mt-1 shrink-0" size={14} />
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}
