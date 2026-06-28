# playsim — one-command stand-up. PokerKit needs Python <3.14, so we pin 3.12.
PY ?= python3.12
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: venv install test run replay tables calibrate health routing explorer scoring-sensitivity agentic agentic-llm docker clean

venv:
	$(PY) -m venv $(VENV)

install: venv
	$(BIN)/pip install -q -r requirements.txt
	$(BIN)/pip install -q -e .

test:
	$(BIN)/pytest -q

run:        ## play the cluster case, write a replayable DB + features
	$(BIN)/python -m playsim.cli run --table case_c --hands 500 --seed 42 \
		--db out/sim.db --features out/features.json

replay:     ## prove the run is byte-identical
	$(BIN)/python -m playsim.cli replay --table case_c --hands 500 --seed 42

routing:    ## Standard-vs-FairPlay counterfactual: does routing improve table health?
	$(BIN)/python -m playsim.cli routing --hands 600 --seed 42

health:     ## play a table out (persistent stacks) and score its health
	$(BIN)/python -m playsim.cli health --table routing_standard --hands 600 --seed 42

calibrate:  ## tune postflop_aggression until realized AF ≈ archetype targets
	$(BIN)/python -m playsim.cli calibrate --rounds 6 --hands 450

tables:
	$(BIN)/python -m playsim.cli tables

explorer:   ## build the self-contained sweep-explorer web UI from out/*.json
	$(BIN)/python analysis/build_sweep_explorer.py
	@echo "open: out/sweep-explorer.html"

scoring-sensitivity:   ## run scoring sensitivity sweep + dashboard
	$(BIN)/python analysis/scoring_sensitivity_sweep.py
	@echo "open: out/scoring-sensitivity-explorer.html"

agentic:   ## run the bounded Standard-vs-FairPlay-liveness experiment loop
	$(BIN)/python -m playsim.cli agentic \
		--spec experiments/standard-vs-fairplay-liveness-agentic.json \
		--out-dir out/agentic

agentic-llm:   ## run the bounded loop with the optional OpenAI planner
	$(BIN)/python -m playsim.cli agentic \
		--spec experiments/standard-vs-fairplay-liveness-agentic.json \
		--out-dir out/agentic-llm \
		--planner llm

docker:
	docker compose run --rm playsim run --table case_c --hands 500 --seed 42 --db /data/sim.db

clean:
	rm -rf $(VENV) out **/__pycache__ *.egg-info
