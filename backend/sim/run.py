"""Entrypoint: config -> run all tables -> write hand histories + player stats.

Run from the repo root:  python backend/sim/run.py --config backend/sim/config/default.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root (backend/sim/ -> backend/ -> root)
sys.path.insert(0, str(ROOT / "backend"))           # make the `sim` package importable

from sim import deck, stats  # noqa: E402
from sim.agents.archetype import Agent, ARCHETYPES  # noqa: E402
from sim.driver import run_table  # noqa: E402
from sim.engine.pokerkit_engine import PokerKitEngine  # noqa: E402
from sim.log import EventLog  # noqa: E402

OUT_DIR = ROOT / "data" / "sim"


def simulate(config: dict):
    log = EventLog()
    blinds = tuple(config["blinds"])
    samples = config.get("equity_samples", 120)
    for idx, table in enumerate(config["tables"]):
        seats = table["seats"]
        agents = [Agent(ARCHETYPES[s["archetype"]], samples) for s in seats]
        player_ids = [s["player_id"] for s in seats]
        run_table(
            table_id=table["table_id"], engine=PokerKitEngine(), agents=agents,
            player_ids=player_ids, blinds=blinds,
            starting_stack=config["starting_stack"],
            hands=config["hands_per_table"],
            table_seed=deck.derive(config["master_seed"], idx),
            log=log)
    player_stats = stats.rollup(log.events, log.results)
    # Attach provenance (archetype) so every stat traces back to its inputs.
    arch_of = {s["player_id"]: s["archetype"]
               for t in config["tables"] for s in t["seats"]}
    for pid, row in player_stats.items():
        row["archetype"] = arch_of.get(pid)
    return log.events, log.results, player_stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "backend" / "sim" / "config" / "default.json"))
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    events, results, player_stats = simulate(config)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "hand_histories.json").write_text(
        json.dumps({"events": events, "results": results}, indent=2) + "\n",
        encoding="utf-8")
    (OUT_DIR / "player_stats.json").write_text(
        json.dumps({"players": player_stats}, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} hand-results · {len(player_stats)} players "
          f"-> {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
