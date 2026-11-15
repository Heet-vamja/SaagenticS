"use client";
import { useEffect, useRef, type ElementType, type ReactNode } from "react";

/**
 * Scroll-triggered entrance, once per element. Server-rendered content stays visible;
 * only elements that start below the fold are hidden after hydration, then revealed.
 * Reduced motion and missing IntersectionObserver show content immediately.
 */
export function Reveal({
  children,
  as: Tag = "div",
  delay = 0,
  className = "",
  ...rest
}: {
  children: ReactNode;
  as?: ElementType;
  delay?: number;
  className?: string;
} & Record<string, unknown>) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (
      !node ||
      typeof IntersectionObserver === "undefined" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      node.getBoundingClientRect().top < window.innerHeight * 0.92
    )
      return;
    node.style.setProperty("--reveal-delay", `${delay}ms`);
    node.classList.add("reveal-pending");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        node.classList.add("reveal-shown");
        node.classList.remove("reveal-pending");
        observer.disconnect();
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [delay]);
  return (
    <Tag ref={ref} className={className} {...rest}>
      {children}
    </Tag>
  );
}
