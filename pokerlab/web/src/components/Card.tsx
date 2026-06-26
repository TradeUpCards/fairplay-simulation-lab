const SUIT: Record<string, string> = { h: "♥", d: "♦", c: "♣", s: "♠" };

const DIMS: Record<string, string> = {
  sm: "w-7 h-10 text-sm",
  md: "w-10 h-14 text-lg",
  lg: "w-14 h-20 text-2xl",
};

export function Card({ c, size = "md" }: { c: string | null; size?: "sm" | "md" | "lg" }) {
  const dims = DIMS[size];
  if (!c) return <div className={`card back ${dims}`} aria-label="hidden card" />;
  const rank = c[0] === "T" ? "10" : c[0];
  const suit = c[1];
  const red = suit === "h" || suit === "d";
  return (
    <div className={`card ${red ? "red" : ""} ${dims} font-bold gap-0.5`} aria-label={c}>
      <span>{rank}</span>
      <span>{SUIT[suit] ?? suit}</span>
    </div>
  );
}
