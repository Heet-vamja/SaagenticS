import { useId } from "react";

/** A bounded, evidence-only score display. An unavailable score stays unfilled. */
export function ReadinessScore({
  value,
  color,
}: {
  value: number | null;
  color: string;
}) {
  const gradientId = useId();
  const score = value === null ? null : Math.max(0, Math.min(100, value));
  // Each tier token (e.g. --score-good) has a lighter "-start" companion.
  const start = color.startsWith("var(--score-")
    ? color.replace(/\)$/, "-start)")
    : color;
  return (
    <div
      className="report-score-display"
      role="img"
      aria-label={
        score === null
          ? "Score unavailable"
          : `Readiness score ${score} out of 100`
      }
    >
      <svg
        className="report-score-ring"
        viewBox="0 0 180 180"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" style={{ stopColor: start }} />
            <stop offset="100%" style={{ stopColor: color }} />
          </linearGradient>
        </defs>
        <circle
          cx="90"
          cy="90"
          r="74"
          fill="none"
          stroke="var(--muted)"
          strokeWidth="14"
        />
        {score !== null && score > 0 && (
          <circle
            cx="90"
            cy="90"
            r="74"
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth="14"
            strokeLinecap="round"
            pathLength="100"
            strokeDasharray="100"
            strokeDashoffset={100 - score}
            transform="rotate(-90 90 90)"
          />
        )}
      </svg>
      <div className="report-score-value">
        <span style={{ color }}>{score === null ? "—" : score}</span>
        <span>out of 100</span>
      </div>
    </div>
  );
}
