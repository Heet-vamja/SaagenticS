"use client";
import { useId } from "react";
export function Tabs({
  items,
  value,
  onChange,
  children,
}: {
  items: { value: string; label: string; count?: number }[];
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  const id = useId();
  return (
    <>
      <div
        role="tablist"
        aria-label="Result sections"
        className="mb-6 flex gap-5 overflow-x-auto border-b"
        onKeyDown={(e) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key))
            return;
          e.preventDefault();
          const buttons = Array.from(
            e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'),
          );
          const index = buttons.indexOf(
            document.activeElement as HTMLButtonElement,
          );
          const next =
            e.key === "Home"
              ? 0
              : e.key === "End"
                ? buttons.length - 1
                : (index + (e.key === "ArrowRight" ? 1 : -1) + buttons.length) %
                  buttons.length;
          buttons[next]?.focus();
          buttons[next]?.click();
        }}
      >
        {items.map((item) => (
          <button
            key={item.value}
            id={`${id}-${item.value}`}
            role="tab"
            aria-selected={value === item.value}
            aria-controls={`${id}-panel`}
            tabIndex={value === item.value ? 0 : -1}
            className={`relative flex min-h-12 shrink-0 items-center gap-2 border-b-2 px-0.5 text-xs ${value === item.value ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"}`}
            onClick={() => onChange(item.value)}
          >
            {item.label}
            {item.count !== undefined && (
              <span
                className={`rounded px-1.5 py-0.5 text-[9px] ${value === item.value ? "bg-accent-soft text-primary" : "bg-muted"}`}
              >
                {item.count}
              </span>
            )}
          </button>
        ))}
      </div>
      <div
        id={`${id}-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-${value}`}
        className="fade-in"
        key={value}
      >
        {children}
      </div>
    </>
  );
}
