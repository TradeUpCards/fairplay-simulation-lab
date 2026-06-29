import { Slide, Stat, Columns, Lead } from "../Slide";
import type { SlideDef } from "../types";

function IndustrySlide() {
  return (
    <Slide
      kicker="The market"
      title="Online poker is a multi-billion-dollar business — and growing"
    >
      <div className="flex flex-col gap-8">
        <Columns cols={3}>
          <Stat
            value="~$6B"
            label="Online poker, 2025"
            sub="global gross gaming revenue"
          />
          <Stat
            value="12–15%"
            label="Projected CAGR"
            sub="through the early 2030s"
            tone="felt"
          />
          <Stat
            value="~$18–22B"
            label="Online poker by ~2034"
            sub="if growth holds"
          />
        </Columns>

        <Lead>Operators compete hard for a finite thing: player time.</Lead>
      </div>
    </Slide>
  );
}

export const industrySlide: SlideDef = {
  id: "industry",
  label: "The market",
  Component: IndustrySlide,
};
