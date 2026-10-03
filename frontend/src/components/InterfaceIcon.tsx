type IconName = "brand" | "right" | "down" | "up" | "up-right" | "down-left" | "left";

const paths: Record<IconName, string> = {
  brand: "M12 2v20M2 12h20M5 5l14 14M5 19 19 5",
  right: "M4 12h16m-6-6 6 6-6 6",
  down: "M12 4v16m-6-6 6 6 6-6",
  up: "M12 20V4m-6 6 6-6 6 6",
  "up-right": "M5 19 19 5M5 5h14v14",
  "down-left": "M19 5 5 19M5 5v14h14",
  left: "M20 12H4m6-6-6 6 6 6",
};

/** Decorative vectors: never fall back to an operating-system emoji font. */
export function InterfaceIcon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={name === "brand" ? 2.8 : 1.5}
      strokeLinecap="square"
      strokeLinejoin="miter"
      className={className}
      style={{ verticalAlign: "-0.125em", flexShrink: 0 }}
    >
      <path d={paths[name]} />
    </svg>
  );
}
