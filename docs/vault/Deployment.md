---
tags: [icc-bot, deployment]
---

# Deployment

Built for **Railway**. The repo has everything Railway needs:

| File | Purpose |
| --- | --- |
| `requirements.txt` | Python dependencies |
| `.python-version` | `3.13`, the version it was tested with |
| `Procfile` | `web: uvicorn main:app --host 0.0.0.0 --port $PORT` |
| `railway.json` | Health check and restart policy |

## Steps

1. Push the repo to GitHub, then in Railway: **New Project → Deploy from GitHub repo**.
2. In the service's **Variables → Raw Editor**, paste the contents of your `.env`. At least `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`; see [[Environment Variables]], and set `PIVOT_LEFT`/`PIVOT_RIGHT` to the chart's swing length.
3. Optional: **Settings → Networking → Generate Domain** to reach the [[Status Endpoint]]. Set `STATUS_TOKEN` first if you don't want it public.
4. Deploy. The logs should show `Connected to Alpaca paper account …` then `Starting 24/7 ICC Scanner`.
5. **Stop any local copy.** Two running bots on one Alpaca account each see the same signals. The order-id guard stops the second one from placing the same entry, but both still manage exits.

## railway.json

```json
{
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 60,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

A deploy is live only once `/health` answers 200. Bad Alpaca keys make startup fail, so the deploy fails visibly instead of running a bot that can't trade.

## Free plan

As of 2026-11-25 ([Railway pricing](https://docs.railway.com/pricing/plans), [Free plan](https://docs.railway.com/pricing/free-plan)):

- **Trial**: 30 days, a one-time $5 credit. Enough for the first month.
- **Free plan** after that: $1 of usage a month, 0.5 GB RAM, 1 vCPU, 1 replica. Services are serverless, but sleep only after 5–10 minutes with **no outbound traffic**. The bot calls Alpaca every 60 s, so it never sleeps.
- **Cost**: RAM is $10 per GB-month. The bot uses about **118 MB** (measured locally; `alpaca-py` loads pandas, ~108 MB before any bot code), so about $1.15 of RAM a month plus a little CPU. That is just over the $1, so on the Free plan it **stops for the last few days of each month** and restarts with the new cycle.
- **Hobby**, $5/month with $5 of usage included, runs it all month.

## Keep it to one replica

Each replica runs its own scanner. The Free plan allows only one anyway; on paid plans, leave replicas at 1.

## Restarts

A restart loses the in-memory counters on the [[Status Endpoint]], but nothing that matters for trading: the duplicate guard and the crypto targets live on Alpaca as order ids ([[Trade Execution]]).

## Logs

Railway's log view is the trade journal:

| Line | Meaning |
| --- | --- |
| `ICC Signal Detected on X: {...}` | The engine fired on the latest closed candle |
| `EXECUTED BUY ...` | Entry placed (with its stop) |
| `TAKE PROFIT X at ~...` | Crypto target reached, position closed |
| `Closed long X on ICC SELL signal.` | Crypto SELL closed a long |
| `Skipping ...` | A check failed; the reason follows |
| `... was already placed, skipping.` | Duplicate after a restart, ignored |
| `Scan failed for X` + traceback | That symbol failed this scan; the others still ran |
