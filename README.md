# OpenTerm — Open-Source Multi-Asset Quantitative Terminal

OpenTerm is an open-source, keyboard-driven quantitative financial workstation built on **FastAPI + DuckDB + Polars** and **React + TypeScript + TradingView Lightweight Charts + TanStack Table**.

## Core Capabilities

- **Mnemonic Command Bar & Linked Multi-Pane Workspace**: Fast keyboard navigation (`/`, `Ctrl+K`, `F2 <Equity>`, `F3 <Crypto>`, `Alt+1..4`, `Alt+L`) with color-coded link groups (`GRP A`, `GRP B`, `GRP C`, `FREE`) and `1x1` / `1x2` / `2x1` / `2x2` split layouts.
- **Unified Multi-Asset Normalization**:
  - **US Equities** (`EQ:US:*`): SEC EDGAR XBRL / US GAAP financials, extended hours, options chain IV & Greeks, top 13F institutional holders.
  - **China A-Shares** (`EQ:SSE:*`, `EQ:SZSE:*`, `EQ:BSE:*`): 6-digit prefix normalization (`.SS`/`.SZ`/`.BJ`), board-aware daily price-limit bands (`±10%` Main, `±20%` ChiNext/STAR, `±30%` BSE, `±5%` ST), strict `T+1` sell lock tracking, and Stock Connect Northbound capital flows (北向资金).
  - **Cryptocurrencies** (`CR:SPOT:*`, `CR:PERP:*`): 24/7 sessions, 8h perpetual funding rates, open interest, basis (bps), CEX/DEX volume split, and DefiLlama TVL/protocol metrics.
- **Analytical Modules**:
  - `DES` — Security Description & Market Microstructure
  - `FA` — Standardized IS/BS/CF (TanStack Table) + Valuation Multiples + Interactive 5x5 DCF Sensitivity Model
  - `GP` — TradingView Lightweight Charts with Polars SMA/EMA/BB/RSI/MACD, Volume Profile (POC), Event Overlays, and WebSocket live tick updates
  - `COMP` — Cross-market FX-normalized Peer Comparison (`USD` / `CNY`)
  - `NEWS` — Bilingual EN/ZH Real-Time News, SEC/CSRC Filings & Sentiment Scoring
  - `PORT` — Multi-Currency Portfolio & Risk Engine (FX P&L attribution, T+1 lock, Sharpe, Sortino, Max Drawdown, Beta, 95%/99% VaR, 252D Correlation Matrix)
  - `BQL` — Programmable Read-Only DuckDB SQL & AST-Sandboxed Python/Polars Backtest Console

## Quick Start

```bash
# Backend
make install-backend
make dev-backend

# Frontend
make install-frontend
make dev-frontend

# Run Backend Unit & E2E Tests
make test
```

To enable live external market adapters (`yfinance`, SEC EDGAR XBRL, `AkShare`, `CCXT`), install optional dependencies (`make install-backend-adapters`) and set `OPENTERM_ENABLE_LIVE_ADAPTERS=true`.
