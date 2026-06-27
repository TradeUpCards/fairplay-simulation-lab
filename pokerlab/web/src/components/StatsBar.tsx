import type { ReactNode } from "react";
import type { SessionStats } from "../types";

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-3">
      <div className="font-mono text-sm leading-tight">{children}</div>
      <div className="text-[10px] uppercase tracking-wider text-faint">{label}</div>
    </div>
  );
}

const signed = (n: number, dp = 1) => `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;
const cls = (n: number) => (n >= 0 ? "text-gain" : "text-loss");

export function StatsBar({ stats }: { stats: SessionStats }) {
  if (stats.hands_played === 0 && stats.walks_won === 0) return null;
  return (
    <div className="flex items-center justify-center divide-x divide-line rounded-xl border border-line bg-surface-2/50 py-2">
      <Item label="hands">{stats.hands_played}</Item>
      <Item label="net">
        <span className={cls(stats.net_bb)}>{signed(stats.net_bb)} bb</span>
      </Item>
      <Item label="bb/100">
        <span className={cls(stats.bb_per_100)}>{signed(stats.bb_per_100, 0)}</span>
      </Item>
      <Item label="record">
        {stats.won}-{stats.lost}
        {stats.tie ? `-${stats.tie}` : ""}
      </Item>
      <Item label="ev lost">
        <span className="text-loss">{stats.ev_lost_bb.toFixed(1)} bb</span>
      </Item>
    </div>
  );
}
