import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] font-semibold tracking-[-.01em] transition-[background-color,color,border-color,box-shadow,transform] duration-200 ease-out focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:pointer-events-none disabled:opacity-50 active:scale-[.98]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-[0_1px_2px_#0e101326] hover:bg-[var(--primary-hover)] hover:shadow-[var(--shadow-glow)] active:bg-[var(--primary-active)]",
        secondary: "bg-accent-soft text-signal hover:bg-accent-soft/70",
        outline:
          "border border-border bg-card text-foreground hover:border-border-strong/40 hover:bg-muted",
        ghost: "text-muted-foreground hover:bg-muted hover:text-foreground",
        ink: "bg-ink text-ink-foreground hover:bg-ink/85 dark:bg-foreground dark:text-background dark:hover:bg-foreground/85",
        lime: "bg-lime text-lime-foreground hover:brightness-95 hover:shadow-[0_10px_24px_-10px_#cbf34acc] active:brightness-90",
      },
      size: {
        default: "min-h-11 h-auto px-5 py-2.5 text-[15px]",
        sm: "min-h-9 h-auto px-4 py-1.5 text-[14px]",
        lg: "min-h-13 h-auto px-7 py-3 text-[16px]",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);
export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}
