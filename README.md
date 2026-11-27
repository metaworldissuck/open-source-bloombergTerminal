# OpenTerm — Open-Source Multi-Asset Quantitative Terminal

OpenTerm is an open-source, keyboard-driven Bloomberg Terminal alternative built on **FastAPI + DuckDB + Polars + WebSockets** and **React + TypeScript + TradingView Lightweight Charts + TanStack Table**.

- **Permanent Web Terminal (GitHub Pages):** `https://metaworldissuck.github.io/open-source-bloombergTerminal/`
- **One-Click Full-Stack Cloud Deploy (FastAPI + DuckDB + Live Adapters):**
  [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/metaworldissuck/open-source-bloombergTerminal)

## Core Functional Modules

- **Mnemonic Command Bar & Linked Multi-Pane Workspace:** `/` or `Ctrl+K` command focus, `F2 <Equity>` / `F3 <Crypto>` / `F4 <FX>`, `Alt+1..4` pane switching, `Alt+L` color-coded link groups (`GRP A`, `GRP B`, `GRP C`, `FREE`), `1x1` / `1x2` / `2x1` / `2x2` layouts.
- **Unified Multi-Asset Normalization & Live Ingestion (`yfinance`, SEC EDGAR, `AkShare`, `CCXT`, `DefiLlama`):**
  - **US Equities (`DES`, `OPT`):** SEC EDGAR 10-K/10-Q/13F, extended hours, full Calls/Puts options straddle chain with IV & Greeks.
  - **China A-Shares (`DES`, `FLOW`):** 6-digit prefix normalization (`.SS`/`.SZ`/`.BJ`), board-aware ±10%/±20%/±30%/±5% 涨停/跌停 bands, strict `T+1` sell lock, Northbound/Southbound capital flows (北向/南向资金), CSRC/exchange notices.
  - **Cryptocurrencies (`DES`, `PERP`):** 24/7 continuous sessions, 8h perpetual funding rates, Open Interest, perp basis (bps), CEX/DEX liquidity split, DefiLlama TVL & active addresses.
- **Deep Analytics (`FA` + 5×5 DCF, `GP` + RSI/MACD + Volume Profile, `COMP`):** Standardized GAAP/CAS/Tokenomics financial statements, interactive DCF sensitivity calculator, candlestick event & limit-hit markers, FX-normalized peer comparisons.
- **Real-Time News & Sentiment (`NEWS`):** Bilingual EN/ZH filings & news feed with ticker tagging and sentiment scoring.
- **Portfolio & Risk Management (`PORT`):** Multi-currency (`USD`/`CNY`/`USDT`) P&L + FX attribution, A-share `T+1` sell lock, Equity Curve & Underwater Drawdown, Sharpe, Sortino, Max Drawdown, Beta, 95%/99% VaR, and 252D Correlation Matrix.
- **Programmable Query Console (`BQL`):** Read-only DuckDB SQL + AST-sandboxed Python/Polars vectorized backtester.

## Local / Docker Quick Start

```bash
# Single-container production build (UI + API + WebSockets on port 8080)
docker build -t openterm .
docker run -p 8080:8080 -e OPENTERM_ENABLE_LIVE_ADAPTERS=true openterm
```
