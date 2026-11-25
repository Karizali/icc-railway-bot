---
tags: [icc-bot, setup]
---

# Getting Started

## Requirements

- **Python 3.10 or newer**; tested on 3.13 (`.python-version`).
- An **Alpaca paper trading** account and its API key and secret (Alpaca dashboard → Paper Trading → API Keys).

## Install

```bash
cd icc-railway-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

```bash
cp .env.example .env
```

Fill in `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`, and set `PIVOT_LEFT`/`PIVOT_RIGHT` to your chart's swing length. All settings: [[Environment Variables]].

## Test

```bash
python -m unittest
```

7 engine tests, no network needed ([[Signal Engine#Tests]]).

## Run

```bash
uvicorn main:app --port 8000
```

The log shows:

```
[INFO] Connected to Alpaca paper account PA... (equity 100000).
[INFO] Starting 24/7 ICC Scanner for ['BTC/USD', 'ETH/USD'] on 15m timeframe...
```

Then open `http://localhost:8000/` for the [[Status Endpoint]].

> [!warning] One bot per account
> Stop the local bot before running the Railway one (or the other way round). They trade the same Alpaca account.

## Trying the engine on your own data

```python
import pandas as pd
from icc_engine import evaluate_icc_structure

df = pd.read_csv("bars.csv", parse_dates=["timestamp"])  # timestamp, high, low, close
print(evaluate_icc_structure(df, left=3, right=3))
```

It returns `None` unless the **last row** completes a setup.
