# PokerKit needs Python <3.14; pin a known-good runtime so stand-up is one command.
FROM python:3.12-slim

WORKDIR /app

# deps first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

# default: play the cluster case and write a replayable run to a mounted volume
ENTRYPOINT ["python", "-m", "playsim.cli"]
CMD ["run", "--table", "case_c", "--hands", "500", "--seed", "42", "--db", "/data/sim.db"]
