---
tags: [icc-bot, architecture]
---

# Architecture

One Python process. FastAPI serves two routes, and its `lifespan` hook checks the Alpaca keys and then runs the scanner as an `asyncio` task in the same process. There is no database: what must survive a restart lives on Alpaca, as order ids ([[Trade Execution]]).

```mermaid
flowchart LR
  subgraph Railway["Railway web service (uvicorn)"]
    API["FastAPI\nGET /  ·  GET /health"]
    Loop["market_scanner_loop()\nevery POLL_INTERVAL_SECONDS"]
    Engine["icc_engine.evaluate_icc_structure()"]
    Exec["execute_paper_trade()\nmanage_crypto_exit()"]
    State[("in memory:\nlast_traded_bar\nbot_status")]
  end
  Crypto["Alpaca crypto data\n(no auth)"]
  Stock["Alpaca stock data\nIEX feed"]
  Trade["Alpaca paper trading\npositions, orders, client ids"]

  Loop -->|"fetch_bars(), latest_price()"| Crypto
  Loop -->|"fetch_bars(), latest_price()"| Stock
  Loop --> Engine
  Loop --> Exec
  Exec --> Trade
  Loop --> State
  API --> State
  API -->|account, positions| Trade
```

## One scan

```mermaid
sequenceDiagram
  participant L as Scanner loop
  participant D as Alpaca data
  participant E as ICC engine
  participant T as Alpaca trading
  loop every 60 s
    loop each symbol (own try/except)
      alt crypto
        L->>T: open icc-sl stop? read target from its id
        L->>D: latest price, close if target reached
      else stock and market closed
        L->>L: skip
      end
      L->>D: fetch_bars(): closed candles only
      L->>E: evaluate_icc_structure()
      E-->>L: signal or None
      alt new signal
        L->>T: order with this client id exists? skip
        L->>T: flatten, then entry and stop
      end
    end
    L->>L: sleep POLL_INTERVAL_SECONDS
  end
```

Alpaca's SDK is blocking, so each symbol's scan runs through `asyncio.to_thread`, which keeps the routes responsive.

## Pieces

| Piece | Where | Note |
| --- | --- | --- |
| Startup | `lifespan` | `get_account()` first: bad keys fail the deploy |
| Scanner loop | `market_scanner_loop`, `scan_symbol` | An error in one symbol is logged and stored in `last_error`; the others still run |
| Data | `fetch_bars`, `latest_price` | [[Market Data]] |
| Signal logic | `icc_engine.py` | [[Signal Engine]] |
| Orders | `execute_paper_trade`, `flatten`, `manage_crypto_exit` | [[Trade Execution]] |
| Routes | `status`, `health` | [[Status Endpoint]] |
| Duplicate guard | `last_traded_bar` in memory, then the entry's `client_order_id` on Alpaca | Survives restarts |
| Caches | `_assets` (per symbol), `_clock` (60 s) | Fewer API calls |
