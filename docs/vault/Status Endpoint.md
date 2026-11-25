---
tags: [icc-bot, api]
---

# Status Endpoint

Two routes. FastAPI's docs are also served at `/docs` and `/openapi.json`.

## `GET /health`

For Railway's health check ([[Deployment#railway.json]]). Returns **200** while the scanner task is running and **503** if it has stopped. It never calls Alpaca.

```json
{"scanner_running": true, "last_scan": "2026-11-25T18:22:22.533986+00:00"}
```

## `GET /`

If `STATUS_TOKEN` is set, it needs `?token=<STATUS_TOKEN>`, otherwise 401.

```json
{
  "status": "running_24_7",
  "mode": "ALPACA_PAPER",
  "symbols": ["BTC/USD", "ETH/USD"],
  "timeframe_minutes": 15,
  "last_scan": "2026-11-25T18:22:22.533986+00:00",
  "signals_triggered": 0,
  "last_signal": null,
  "last_error": null,
  "equity": "100000",
  "buying_power": "200000",
  "positions": []
}
```

| Field | Source |
| --- | --- |
| `status` | `running_24_7`, or `scanner_stopped` if the scanner task has ended |
| `symbols`, `timeframe_minutes` | [[Environment Variables]] |
| `last_scan` | Start of the latest scan (UTC) |
| `signals_triggered` | Entries placed since the process started |
| `last_signal` | The last entry, with `symbol`, `qty`, and `order_id` |
| `last_error` | The latest per-symbol scan error, with time and symbol |
| `equity`, `buying_power`, `positions` | Live from Alpaca |

If Alpaca can't be reached, the page still loads, with `account_error` in place of the account fields. The counters reset on every restart.

Without `STATUS_TOKEN`, anyone with the URL sees the paper account's equity and positions.
