from __future__ import annotations

import json
import math
import random
from datetime import UTC, date, datetime, timedelta
from typing import Any

import polars as pl

from app.normalization.cn_microstructure import compute_cn_price_limits, compute_settlement_date
from app.normalization.sentiment import score_financial_sentiment
from app.storage.duckdb_engine import DuckDBEngine

INSTRUMENTS_SEED: list[dict[str, Any]] = [
    # --- US EQUITIES ---
    {
        "instrument_id": "EQ:US:AAPL",
        "asset_class": "EQUITY",
        "market": "US",
        "exchange_mic": "XNAS",
        "native_symbol": "AAPL",
        "display_name": "Apple Inc.",
        "display_name_local": None,
        "base_currency": "USD",
        "sector": "Information Technology",
        "industry": "Consumer Electronics & Ecosystem",
        "settlement_rule": "T+1_US",
        "lot_size": 1.0,
        "price_limit_pct": None,
        "trading_calendar_id": "XNYS",
        "description": (
            "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, "
            "wearables, and high-margin recurring services (App Store, iCloud, Apple Pay, Apple Silicon). "
            "Flagship US mega-cap equity with deep options liquidity and institutional 13F ownership."
        ),
        "microstructure_meta": {
            "cik": "0000320193",
            "isin": "US0378331005",
            "exchange": "NASDAQ GS",
            "supports_extended_hours": True,
            "has_options": True,
            "shares_outstanding": 15_115_000_000,
            "free_float_pct": 99.8,
            "dividend_yield_pct": 0.44,
            "beta_5y": 1.18,
            "pre_market_price": 235.12,
            "post_market_price": 234.88,
            "next_earnings_date": "2027-01-29",
        },
        "aliases": [
            ("BLOOMBERG", "AAPL US"),
            ("BLOOMBERG", "AAPL US EQUITY"),
            ("YAHOO", "AAPL"),
            ("CIK", "0000320193"),
            ("ISIN", "US0378331005"),
        ],
        "seed_px": 178.0,
        "drift": 0.00055,
        "vol": 0.0145,
        "base_vol": 52_000_000.0,
    },
    {
        "instrument_id": "EQ:US:NVDA",
        "asset_class": "EQUITY",
        "market": "US",
        "exchange_mic": "XNAS",
        "native_symbol": "NVDA",
        "display_name": "NVIDIA Corporation",
        "display_name_local": None,
        "base_currency": "USD",
        "sector": "Information Technology",
        "industry": "Semiconductors & AI Compute",
        "settlement_rule": "T+1_US",
        "lot_size": 1.0,
        "price_limit_pct": None,
        "trading_calendar_id": "XNYS",
        "description": (
            "NVIDIA Corporation provides accelerated computing GPUs, CUDA software stack, InfiniBand/NVLink "
            "networking, and full-stack AI data center platforms powering frontier model training and inference."
        ),
        "microstructure_meta": {
            "cik": "0001045810",
            "isin": "US67066G1040",
            "exchange": "NASDAQ GS",
            "supports_extended_hours": True,
            "has_options": True,
            "shares_outstanding": 24_530_000_000,
            "free_float_pct": 96.1,
            "dividend_yield_pct": 0.03,
            "beta_5y": 1.66,
            "pre_market_price": 149.40,
            "post_market_price": 148.95,
            "next_earnings_date": "2027-02-24",
        },
        "aliases": [
            ("BLOOMBERG", "NVDA US"),
            ("BLOOMBERG", "NVDA US EQUITY"),
            ("YAHOO", "NVDA"),
            ("CIK", "0001045810"),
        ],
        "seed_px": 62.0,
        "drift": 0.0017,
        "vol": 0.028,
        "base_vol": 240_000_000.0,
    },
    {
        "instrument_id": "EQ:US:MSFT",
        "asset_class": "EQUITY",
        "market": "US",
        "exchange_mic": "XNAS",
        "native_symbol": "MSFT",
        "display_name": "Microsoft Corporation",
        "display_name_local": None,
        "base_currency": "USD",
        "sector": "Information Technology",
        "industry": "Enterprise Software & Cloud",
        "settlement_rule": "T+1_US",
        "lot_size": 1.0,
        "price_limit_pct": None,
        "trading_calendar_id": "XNYS",
        "description": (
            "Microsoft develops Azure cloud infrastructure, M365 productivity suites, GitHub developer tools, "
            "and enterprise Copilot AI workloads with fortress AAA balance sheet characteristics."
        ),
        "microstructure_meta": {
            "cik": "0000789019",
            "isin": "US5949181045",
            "exchange": "NASDAQ GS",
            "supports_extended_hours": True,
            "has_options": True,
            "shares_outstanding": 7_434_000_000,
            "free_float_pct": 99.7,
            "dividend_yield_pct": 0.72,
            "beta_5y": 0.94,
            "pre_market_price": 452.10,
            "post_market_price": 451.40,
            "next_earnings_date": "2027-01-27",
        },
        "aliases": [
            ("BLOOMBERG", "MSFT US"),
            ("BLOOMBERG", "MSFT US EQUITY"),
            ("YAHOO", "MSFT"),
            ("CIK", "0000789019"),
        ],
        "seed_px": 370.0,
        "drift": 0.00042,
        "vol": 0.013,
        "base_vol": 22_000_000.0,
    },
    {
        "instrument_id": "EQ:US:SPY",
        "asset_class": "INDEX",
        "market": "US",
        "exchange_mic": "ARCX",
        "native_symbol": "SPY",
        "display_name": "SPDR S&P 500 ETF Trust",
        "display_name_local": None,
        "base_currency": "USD",
        "sector": "Benchmark Index ETF",
        "industry": "US Large Cap Equity",
        "settlement_rule": "T+1_US",
        "lot_size": 1.0,
        "price_limit_pct": None,
        "trading_calendar_id": "XNYS",
        "description": "Primary institutional benchmark ETF tracking the S&P 500 Index.",
        "microstructure_meta": {
            "cik": "0000884394",
            "exchange": "NYSE Arca",
            "supports_extended_hours": True,
            "has_options": True,
            "shares_outstanding": 1_010_000_000,
            "free_float_pct": 100.0,
            "dividend_yield_pct": 1.21,
            "beta_5y": 1.0,
        },
        "aliases": [("BLOOMBERG", "SPY US"), ("YAHOO", "SPY")],
        "seed_px": 478.0,
        "drift": 0.00045,
        "vol": 0.0095,
        "base_vol": 65_000_000.0,
    },
    # --- CHINA A-SHARES (SSE / SZSE / BSE) ---
    {
        "instrument_id": "EQ:SSE:600519",
        "asset_class": "EQUITY",
        "market": "CN_ASHARE",
        "exchange_mic": "XSHG",
        "native_symbol": "600519",
        "display_name": "Kweichow Moutai Co., Ltd.",
        "display_name_local": "贵州茅台",
        "base_currency": "CNY",
        "sector": "Consumer Staples",
        "industry": "Distillers & Vintners (Baijiu)",
        "settlement_rule": "T+1_CN_STRICT",
        "lot_size": 100.0,
        "price_limit_pct": 0.10,
        "trading_calendar_id": "XSHG",
        "description": (
            "Kweichow Moutai (贵州茅台) produces flagship Feitian Maotai ultra-premium sauce-aroma baijiu "
            "in Guizhou, China. Bellwether CSI 300 constituent traded on SSE Main Board under strict T+1 "
            "settlement and +/-10% daily price limits with heavy Stock Connect Northbound (北向资金) participation."
        ),
        "microstructure_meta": {
            "board": "MAIN",
            "yahoo_ticker": "600519.SS",
            "csrc_code": "C15",
            "is_st": False,
            "is_northbound_eligible": True,
            "t_plus_1_sell_lock": True,
            "shares_outstanding": 1_256_197_800,
            "free_float_pct": 45.8,
            "dividend_yield_pct": 3.45,
            "beta_5y": 0.88,
        },
        "aliases": [
            ("BLOOMBERG", "600519 CH"),
            ("BLOOMBERG", "600519 CH EQUITY"),
            ("YAHOO", "600519.SS"),
            ("CSRC", "SH600519"),
        ],
        "seed_px": 1620.0,
        "drift": 0.00018,
        "vol": 0.0155,
        "base_vol": 3_400_000.0,
    },
    {
        "instrument_id": "EQ:SZSE:300750",
        "asset_class": "EQUITY",
        "market": "CN_ASHARE",
        "exchange_mic": "XSHE",
        "native_symbol": "300750",
        "display_name": "Contemporary Amperex Technology (CATL)",
        "display_name_local": "宁德时代",
        "base_currency": "CNY",
        "sector": "Industrials",
        "industry": "EV Batteries & Energy Storage",
        "settlement_rule": "T+1_CN_STRICT",
        "lot_size": 100.0,
        "price_limit_pct": 0.20,
        "trading_calendar_id": "XSHE",
        "description": (
            "CATL (宁德时代) is the world's largest lithium-ion EV and grid-scale energy storage battery "
            "manufacturer. Listed on Shenzhen ChiNext (创业板) with +/-20% daily price limit bands and "
            "T+1 settlement rules."
        ),
        "microstructure_meta": {
            "board": "CHINEXT",
            "yahoo_ticker": "300750.SZ",
            "csrc_code": "C38",
            "is_st": False,
            "is_northbound_eligible": True,
            "t_plus_1_sell_lock": True,
            "shares_outstanding": 4_403_466_458,
            "free_float_pct": 68.4,
            "dividend_yield_pct": 2.15,
            "beta_5y": 1.24,
        },
        "aliases": [
            ("BLOOMBERG", "300750 CH"),
            ("BLOOMBERG", "300750 CH EQUITY"),
            ("YAHOO", "300750.SZ"),
            ("CSRC", "SZ300750"),
        ],
        "seed_px": 182.0,
        "drift": 0.00068,
        "vol": 0.023,
        "base_vol": 28_000_000.0,
    },
    {
        "instrument_id": "EQ:SSE:688981",
        "asset_class": "EQUITY",
        "market": "CN_ASHARE",
        "exchange_mic": "XSHG",
        "native_symbol": "688981",
        "display_name": "SMIC (Semiconductor Mfg Intl)",
        "display_name_local": "中芯国际",
        "base_currency": "CNY",
        "sector": "Information Technology",
        "industry": "Semiconductor Foundry",
        "settlement_rule": "T+1_CN_STRICT",
        "lot_size": 200.0,
        "price_limit_pct": 0.20,
        "trading_calendar_id": "XSHG",
        "description": (
            "SMIC (中芯国际) is mainland China's premier semiconductor wafer foundry, listed on SSE STAR "
            "Market (科创板) with +/-20% daily price limit bands and 200-share minimum order lot."
        ),
        "microstructure_meta": {
            "board": "STAR",
            "yahoo_ticker": "688981.SS",
            "csrc_code": "C39",
            "is_st": False,
            "is_northbound_eligible": True,
            "t_plus_1_sell_lock": True,
            "shares_outstanding": 7_975_000_000,
            "free_float_pct": 54.0,
            "dividend_yield_pct": 0.0,
            "beta_5y": 1.42,
        },
        "aliases": [
            ("BLOOMBERG", "688981 CH"),
            ("BLOOMBERG", "688981 CH EQUITY"),
            ("YAHOO", "688981.SS"),
        ],
        "seed_px": 54.0,
        "drift": 0.00085,
        "vol": 0.029,
        "base_vol": 65_000_000.0,
    },
    {
        "instrument_id": "EQ:BSE:430047",
        "asset_class": "EQUITY",
        "market": "CN_ASHARE",
        "exchange_mic": "XBSE",
        "native_symbol": "430047",
        "display_name": "Beijing Northland Biotech",
        "display_name_local": "诺思兰德",
        "base_currency": "CNY",
        "sector": "Health Care",
        "industry": "Biotechnology (BSE)",
        "settlement_rule": "T+1_CN_STRICT",
        "lot_size": 100.0,
        "price_limit_pct": 0.30,
        "trading_calendar_id": "XBSE",
        "description": (
            "Beijing Northland Biotech (诺思兰德) develops gene therapy and recombinant protein biologics. "
            "Traded on the Beijing Stock Exchange (北交所 .BJ) with wide +/-30% daily price limits."
        ),
        "microstructure_meta": {
            "board": "BSE",
            "yahoo_ticker": "430047.BJ",
            "csrc_code": "C27",
            "is_st": False,
            "is_northbound_eligible": False,
            "t_plus_1_sell_lock": True,
            "shares_outstanding": 274_200_000,
            "free_float_pct": 71.2,
            "dividend_yield_pct": 0.0,
            "beta_5y": 1.35,
        },
        "aliases": [
            ("BLOOMBERG", "430047 CH"),
            ("BLOOMBERG", "430047 BJ"),
            ("YAHOO", "430047.BJ"),
        ],
        "seed_px": 14.5,
        "drift": 0.0004,
        "vol": 0.036,
        "base_vol": 4_200_000.0,
    },
    # --- CRYPTOCURRENCIES ---
    {
        "instrument_id": "CR:SPOT:BTC-USD",
        "asset_class": "CRYPTO",
        "market": "CRYPTO",
        "exchange_mic": "AGG",
        "native_symbol": "BTC-USD",
        "display_name": "Bitcoin Spot (Aggregate)",
        "display_name_local": "比特币",
        "base_currency": "USD",
        "sector": "Digital Assets",
        "industry": "Layer-1 Store of Value",
        "settlement_rule": "T+0_INSTANT",
        "lot_size": 0.00001,
        "price_limit_pct": None,
        "trading_calendar_id": "24_7",
        "description": (
            "Bitcoin (BTC) decentralized proof-of-work monetary network trading 24/7 globally across "
            "spot CEXs, regulated US spot ETFs, and perpetual futures venues with 21M hard supply cap."
        ),
        "microstructure_meta": {
            "contract_type": "SPOT",
            "base_asset": "BTC",
            "quote_asset": "USD",
            "chain": "bitcoin",
            "circulating_supply": 19_940_000,
            "max_supply": 21_000_000,
            "funding_interval_hours": 8,
            "primary_venues": ["Binance", "Coinbase", "OKX", "CME"],
            "beta_5y": 1.85,
        },
        "aliases": [
            ("BLOOMBERG", "BTC-USD"),
            ("BLOOMBERG", "BTC-USD CRYPTO"),
            ("BLOOMBERG", "XBTUSD"),
            ("COINGECKO", "bitcoin"),
            ("CCXT", "BTC/USDT"),
        ],
        "seed_px": 51_000.0,
        "drift": 0.0012,
        "vol": 0.0285,
        "base_vol": 420_000.0,
    },
    {
        "instrument_id": "CR:SPOT:ETH-USD",
        "asset_class": "CRYPTO",
        "market": "CRYPTO",
        "exchange_mic": "AGG",
        "native_symbol": "ETH-USD",
        "display_name": "Ethereum Spot (Aggregate)",
        "display_name_local": "以太坊",
        "base_currency": "USD",
        "sector": "Digital Assets",
        "industry": "Smart Contract L1 & DeFi Settlement",
        "settlement_rule": "T+0_INSTANT",
        "lot_size": 0.0001,
        "price_limit_pct": None,
        "trading_calendar_id": "24_7",
        "description": (
            "Ethereum (ETH) programmable proof-of-stake L1 settlement layer hosting the largest DeFi TVL, "
            "stablecoin float, and L2 rollup ecosystem with EIP-1559 fee burn tokenomics."
        ),
        "microstructure_meta": {
            "contract_type": "SPOT",
            "base_asset": "ETH",
            "quote_asset": "USD",
            "chain": "ethereum",
            "circulating_supply": 120_420_000,
            "max_supply": None,
            "funding_interval_hours": 8,
            "primary_venues": ["Binance", "Coinbase", "Uniswap v3", "OKX"],
            "beta_5y": 2.05,
        },
        "aliases": [
            ("BLOOMBERG", "ETH-USD"),
            ("BLOOMBERG", "ETH-USD CRYPTO"),
            ("COINGECKO", "ethereum"),
            ("CCXT", "ETH/USDT"),
        ],
        "seed_px": 2_850.0,
        "drift": 0.00065,
        "vol": 0.034,
        "base_vol": 5_800_000.0,
    },
    {
        "instrument_id": "CR:SPOT:SOL-USD",
        "asset_class": "CRYPTO",
        "market": "CRYPTO",
        "exchange_mic": "AGG",
        "native_symbol": "SOL-USD",
        "display_name": "Solana Spot (Aggregate)",
        "display_name_local": "索拉纳",
        "base_currency": "USD",
        "sector": "Digital Assets",
        "industry": "High-Throughput L1 Execution",
        "settlement_rule": "T+0_INSTANT",
        "lot_size": 0.01,
        "price_limit_pct": None,
        "trading_calendar_id": "24_7",
        "description": (
            "Solana (SOL) high-throughput monolithic L1 blockchain with sub-second finality, dominant "
            "on-chain DEX spot volume (Raydium/Orca/Jupiter), and high daily active addresses."
        ),
        "microstructure_meta": {
            "contract_type": "SPOT",
            "base_asset": "SOL",
            "quote_asset": "USD",
            "chain": "solana",
            "circulating_supply": 475_000_000,
            "max_supply": None,
            "funding_interval_hours": 8,
            "primary_venues": ["Binance", "Coinbase", "Raydium", "Bybit"],
            "beta_5y": 2.45,
        },
        "aliases": [
            ("BLOOMBERG", "SOL-USD"),
            ("BLOOMBERG", "SOL-USD CRYPTO"),
            ("COINGECKO", "solana"),
            ("CCXT", "SOL/USDT"),
        ],
        "seed_px": 118.0,
        "drift": 0.0011,
        "vol": 0.043,
        "base_vol": 28_000_000.0,
    },
    {
        "instrument_id": "CR:PERP:BINANCE:BTC-USDT",
        "asset_class": "CRYPTO",
        "market": "CRYPTO",
        "exchange_mic": "BINANCE",
        "native_symbol": "BTC-PERP",
        "display_name": "Bitcoin USDT Perpetual Futures (Binance)",
        "display_name_local": "比特币永续合约",
        "base_currency": "USDT",
        "sector": "Crypto Derivatives",
        "industry": "Perpetual Swaps (8h Funding)",
        "settlement_rule": "T+0_INSTANT",
        "lot_size": 0.001,
        "price_limit_pct": None,
        "trading_calendar_id": "24_7",
        "description": (
            "Linear USDT-margined Bitcoin Perpetual Futures on Binance with 8-hour funding rate "
            "settlement anchoring mark price to composite spot index."
        ),
        "microstructure_meta": {
            "contract_type": "PERP",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "venue": "BINANCE",
            "funding_interval_hours": 8,
            "max_leverage": 125,
            "beta_5y": 1.88,
        },
        "aliases": [
            ("BLOOMBERG", "BTC-PERP"),
            ("BLOOMBERG", "BTC-PERP CRYPTO"),
            ("CCXT", "BTC/USDT:USDT"),
        ],
        "seed_px": 51_060.0,
        "drift": 0.0012,
        "vol": 0.029,
        "base_vol": 680_000.0,
    },
]


def _seed_financials_profiles() -> dict[str, dict[str, Any]]:
    """Multi-year canonical financials (FY2021-FY2025) in native reporting currency."""
    return {
        "EQ:US:AAPL": {
            "std": "US_GAAP",
            "ccy": "USD",
            "shares": 15_115_000_000,
            "annual": [
                (2022, 394.33e9, 170.78e9, 130.54e9, 119.44e9, 99.80e9, 352.76e9, 120.07e9, 48.30e9, 50.67e9, 122.15e9, 10.71e9),
                (2023, 383.29e9, 169.15e9, 125.82e9, 114.30e9, 97.00e9, 352.58e9, 111.09e9, 61.56e9, 62.15e9, 110.54e9, 10.96e9),
                (2024, 391.04e9, 180.68e9, 134.66e9, 123.22e9, 93.74e9, 364.98e9, 106.63e9, 65.17e9, 56.95e9, 118.25e9, 9.45e9),
                (2025, 416.80e9, 195.90e9, 145.90e9, 134.10e9, 109.20e9, 378.40e9, 101.50e9, 71.20e9, 68.80e9, 128.40e9, 10.20e9),
            ],
        },
        "EQ:US:NVDA": {
            "std": "US_GAAP",
            "ccy": "USD",
            "shares": 24_530_000_000,
            "annual": [
                (2022, 26.91e9, 17.48e9, 11.22e9, 10.04e9, 9.75e9, 44.19e9, 10.95e9, 21.21e9, 26.61e9, 9.11e9, 0.98e9),
                (2023, 26.97e9, 15.36e9, 5.77e9, 4.22e9, 4.37e9, 41.18e9, 10.95e9, 13.30e9, 22.10e9, 5.64e9, 1.83e9),
                (2024, 60.92e9, 44.30e9, 34.48e9, 32.97e9, 29.76e9, 65.73e9, 9.71e9, 25.98e9, 42.98e9, 28.09e9, 1.07e9),
                (2025, 130.50e9, 97.85e9, 83.60e9, 81.45e9, 72.88e9, 111.60e9, 8.46e9, 43.21e9, 79.33e9, 64.09e9, 3.24e9),
            ],
        },
        "EQ:US:MSFT": {
            "std": "US_GAAP",
            "ccy": "USD",
            "shares": 7_434_000_000,
            "annual": [
                (2022, 198.27e9, 135.62e9, 97.84e9, 83.38e9, 72.74e9, 364.84e9, 61.27e9, 104.76e9, 166.54e9, 89.04e9, 23.89e9),
                (2023, 211.92e9, 146.05e9, 102.38e9, 88.52e9, 72.36e9, 411.98e9, 59.97e9, 111.26e9, 206.22e9, 87.58e9, 28.11e9),
                (2024, 245.12e9, 171.01e9, 129.43e9, 109.43e9, 88.14e9, 512.16e9, 67.13e9, 75.54e9, 268.48e9, 118.55e9, 44.48e9),
                (2025, 279.40e9, 194.20e9, 148.10e9, 124.80e9, 101.60e9, 565.30e9, 63.40e9, 84.10e9, 312.50e9, 134.80e9, 58.20e9),
            ],
        },
        "EQ:SSE:600519": {
            "std": "CN_CAS",
            "ccy": "CNY",
            "shares": 1_256_197_800,
            "annual": [
                (2022, 127.55e9, 117.19e9, 90.85e9, 88.10e9, 62.72e9, 254.36e9, 0.48e9, 159.42e9, 197.48e9, 36.70e9, 5.31e9),
                (2023, 150.56e9, 138.45e9, 107.60e9, 104.22e9, 74.73e9, 272.70e9, 0.42e9, 171.20e9, 215.67e9, 66.59e9, 4.92e9),
                (2024, 174.14e9, 160.04e9, 124.10e9, 119.65e9, 86.23e9, 298.94e9, 0.39e9, 186.50e9, 233.11e9, 92.46e9, 5.65e9),
                (2025, 191.20e9, 175.80e9, 136.40e9, 131.50e9, 94.80e9, 321.40e9, 0.35e9, 201.80e9, 252.40e9, 98.10e9, 5.90e9),
            ],
        },
        "EQ:SZSE:300750": {
            "std": "CN_CAS",
            "ccy": "CNY",
            "shares": 4_403_466_458,
            "annual": [
                (2022, 328.59e9, 66.54e9, 49.40e9, 36.12e9, 30.73e9, 600.95e9, 119.50e9, 191.04e9, 164.48e9, 61.21e9, 48.22e9),
                (2023, 400.92e9, 91.85e9, 74.20e9, 54.05e9, 44.12e9, 717.17e9, 128.40e9, 264.31e9, 197.71e9, 92.83e9, 33.62e9),
                (2024, 362.01e9, 88.50e9, 81.90e9, 60.80e9, 50.74e9, 786.66e9, 121.20e9, 303.51e9, 246.93e9, 96.99e9, 31.18e9),
                (2025, 418.50e9, 104.60e9, 95.40e9, 72.10e9, 59.80e9, 845.20e9, 114.80e9, 338.90e9, 286.40e9, 108.50e9, 34.20e9),
            ],
        },
        "EQ:SSE:688981": {
            "std": "CN_CAS",
            "ccy": "CNY",
            "shares": 7_975_000_000,
            "annual": [
                (2022, 49.52e9, 18.88e9, 29.10e9, 13.80e9, 12.13e9, 305.10e9, 62.40e9, 98.20e9, 134.90e9, 36.20e9, 43.10e9),
                (2023, 45.25e9, 8.73e9, 23.80e9, 5.60e9, 4.82e9, 338.60e9, 78.50e9, 89.10e9, 142.30e9, 24.10e9, 52.80e9),
                (2024, 57.80e9, 10.40e9, 28.90e9, 6.20e9, 3.70e9, 355.40e9, 84.20e9, 82.40e9, 148.60e9, 26.80e9, 51.40e9),
                (2025, 68.40e9, 14.36e9, 35.10e9, 9.85e9, 6.45e9, 379.20e9, 86.10e9, 88.50e9, 156.20e9, 32.40e9, 47.90e9),
            ],
        },
        "EQ:BSE:430047": {
            "std": "CN_CAS",
            "ccy": "CNY",
            "shares": 274_200_000,
            "annual": [
                (2022, 0.068e9, 0.042e9, -0.052e9, -0.061e9, -0.063e9, 0.58e9, 0.04e9, 0.24e9, 0.45e9, -0.048e9, 0.032e9),
                (2023, 0.072e9, 0.045e9, -0.041e9, -0.049e9, -0.051e9, 0.64e9, 0.05e9, 0.28e9, 0.49e9, -0.039e9, 0.029e9),
                (2024, 0.089e9, 0.057e9, -0.025e9, -0.033e9, -0.035e9, 0.71e9, 0.05e9, 0.31e9, 0.53e9, -0.022e9, 0.024e9),
                (2025, 0.138e9, 0.094e9, 0.012e9, 0.004e9, 0.003e9, 0.79e9, 0.04e9, 0.35e9, 0.58e9, 0.015e9, 0.021e9),
            ],
        },
        "CR:SPOT:BTC-USD": {
            "std": "ONCHAIN_TOKENOMICS",
            "ccy": "USD",
            "shares": 19_940_000,
            "annual": [
                (2022, 0.14e9, 0.14e9, 0.14e9, 0.14e9, 0.14e9, 320e9, 0.0, 0.0, 320e9, 0.14e9, 0.0),
                (2023, 0.79e9, 0.79e9, 0.79e9, 0.79e9, 0.79e9, 825e9, 0.0, 0.0, 825e9, 0.79e9, 0.0),
                (2024, 0.94e9, 0.94e9, 0.94e9, 0.94e9, 0.94e9, 1850e9, 0.0, 0.0, 1850e9, 0.94e9, 0.0),
                (2025, 1.28e9, 1.28e9, 1.28e9, 1.28e9, 1.28e9, 2140e9, 0.0, 0.0, 2140e9, 1.28e9, 0.0),
            ],
        },
        "CR:SPOT:ETH-USD": {
            "std": "ONCHAIN_TOKENOMICS",
            "ccy": "USD",
            "shares": 120_420_000,
            "annual": [
                (2022, 4.30e9, 3.85e9, 3.85e9, 3.85e9, 1.85e9, 145e9, 0.0, 28e9, 145e9, 3.85e9, 0.0),
                (2023, 2.41e9, 2.02e9, 2.02e9, 2.02e9, 0.72e9, 274e9, 0.0, 39e9, 274e9, 2.02e9, 0.0),
                (2024, 2.68e9, 2.15e9, 2.15e9, 2.15e9, 0.64e9, 410e9, 0.0, 66e9, 410e9, 2.15e9, 0.0),
                (2025, 3.45e9, 2.82e9, 2.82e9, 2.82e9, 1.18e9, 480e9, 0.0, 84e9, 480e9, 2.82e9, 0.0),
            ],
        },
        "CR:SPOT:SOL-USD": {
            "std": "ONCHAIN_TOKENOMICS",
            "ccy": "USD",
            "shares": 475_000_000,
            "annual": [
                (2022, 0.03e9, 0.015e9, 0.015e9, 0.015e9, -0.35e9, 8e9, 0.0, 0.4e9, 8e9, 0.015e9, 0.0),
                (2023, 0.06e9, 0.03e9, 0.03e9, 0.03e9, -0.28e9, 43e9, 0.0, 1.5e9, 43e9, 0.03e9, 0.0),
                (2024, 0.76e9, 0.38e9, 0.38e9, 0.38e9, 0.05e9, 98e9, 0.0, 8.8e9, 98e9, 0.38e9, 0.0),
                (2025, 1.62e9, 0.81e9, 0.81e9, 0.81e9, 0.34e9, 128e9, 0.0, 14.2e9, 128e9, 0.81e9, 0.0),
            ],
        },
    }


def seed_database_if_empty(db: DuckDBEngine) -> None:
    """Populate DuckDB with deterministic, multi-asset institutional-grade seed data if empty."""
    existing = db.query_dicts("SELECT COUNT(*) AS cnt FROM dim_instruments")[0]["cnt"]
    if existing > 0:
        return

    now_utc = datetime.now(UTC)
    today = now_utc.date()
    rng = random.Random(20261127)

    # 1. Instruments & Aliases
    inst_rows: list[tuple[Any, ...]] = []
    alias_rows: list[tuple[Any, ...]] = []
    for item in INSTRUMENTS_SEED:
        inst_rows.append(
            (
                item["instrument_id"],
                item["asset_class"],
                item["market"],
                item["exchange_mic"],
                item["native_symbol"],
                item["display_name"],
                item["display_name_local"],
                item["base_currency"],
                item["sector"],
                item["industry"],
                item["settlement_rule"],
                item["lot_size"],
                item["price_limit_pct"],
                item["trading_calendar_id"],
                True,
                item["description"],
                json.dumps(item["microstructure_meta"]),
                now_utc,
            )
        )
        for scheme, val in item["aliases"]:
            alias_rows.append((scheme, val, item["instrument_id"]))

    db.executemany(
        """
        INSERT OR REPLACE INTO dim_instruments VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        inst_rows,
    )
    db.executemany("INSERT OR REPLACE INTO dim_instrument_aliases VALUES (?, ?, ?)", alias_rows)

    # 2. Daily FX Rates (420 calendar days)
    fx_rows: list[tuple[Any, ...]] = []
    usd_cny = 7.21
    for i in range(420, -1, -1):
        d = today - timedelta(days=i)
        ts = datetime(d.year, d.month, d.day, 16, 0, tzinfo=UTC)
        usd_cny = max(6.95, min(7.42, usd_cny + rng.gauss(0.0, 0.0045)))
        cny_usd = 1.0 / usd_cny
        fx_rows.extend(
            [
                ("USD", "CNY", ts, round(usd_cny, 5)),
                ("CNY", "USD", ts, round(cny_usd, 6)),
                ("USD", "USD", ts, 1.0),
                ("CNY", "CNY", ts, 1.0),
                ("USDT", "USD", ts, round(1.0 + rng.gauss(0.0, 0.0002), 5)),
                ("USDT", "CNY", ts, round(usd_cny, 5)),
                ("HKD", "USD", ts, 0.1282),
            ]
        )
    db.bulk_insert_polars(
        "fact_fx_rates",
        pl.DataFrame(fx_rows, schema=["base_ccy", "quote_ccy", "ts_utc", "rate"], orient="row"),
    )

    # 3. Multi-Asset Correlated Daily OHLCV + Microstructure Facts
    # Generate common macro factor so portfolio correlation matrix has realistic structure
    total_days = 420
    macro_factors = [rng.gauss(0.0, 1.0) for _ in range(total_days + 1)]
    china_factors = [rng.gauss(0.0, 1.0) for _ in range(total_days + 1)]
    crypto_factors = [rng.gauss(0.0, 1.0) for _ in range(total_days + 1)]

    ohlcv_rows: list[tuple[Any, ...]] = []
    cn_micro_rows: list[tuple[Any, ...]] = []
    crypto_metric_rows: list[tuple[Any, ...]] = []
    latest_prices: dict[str, float] = {}

    for item in INSTRUMENTS_SEED:
        iid = item["instrument_id"]
        mkt = item["market"]
        px = float(item["seed_px"])
        drift = float(item["drift"])
        vol = float(item["vol"])
        base_vol = float(item["base_vol"])
        limit_pct = item["price_limit_pct"]
        nb_shares = 95_000_000.0 if iid == "EQ:SSE:600519" else 410_000_000.0
        oi_usd = 18.5e9 if "BTC" in iid else (9.2e9 if "ETH" in iid else 3.1e9)
        tvl_usd = 0.0 if "BTC" in iid else (82.0e9 if "ETH" in iid else 14.5e9)

        for idx in range(total_days, -1, -1):
            d = today - timedelta(days=idx)
            # Equities skip weekends; Crypto trades 24/7
            if mkt != "CRYPTO" and d.weekday() >= 5:
                continue

            f_idx = total_days - idx
            if mkt == "US":
                shock = 0.62 * macro_factors[f_idx] + 0.78 * rng.gauss(0.0, 1.0)
            elif mkt == "CN_ASHARE":
                shock = 0.25 * macro_factors[f_idx] + 0.60 * china_factors[f_idx] + 0.76 * rng.gauss(0.0, 1.0)
            else:
                shock = 0.38 * macro_factors[f_idx] + 0.70 * crypto_factors[f_idx] + 0.60 * rng.gauss(0.0, 1.0)

            prev_close = px
            ret = drift + vol * shock
            # Inject an occasional realistic CN limit-up / limit-down session
            if mkt == "CN_ASHARE" and limit_pct and f_idx in (310, 392):
                ret = limit_pct if f_idx == 392 else -limit_pct

            raw_close = max(0.5, prev_close * math.exp(ret))

            # Enforce China A-Share price limit clamping
            if mkt == "CN_ASHARE" and limit_pct:
                band = compute_cn_price_limits(prev_close, raw_close, limit_pct)
                close_px = min(band.limit_up, max(band.limit_down, round(raw_close, 2)))
                open_px = round(
                    min(band.limit_up, max(band.limit_down, prev_close * (1.0 + rng.gauss(0.0, vol * 0.35)))),
                    2,
                )
                high_px = round(min(band.limit_up, max(open_px, close_px) * (1.0 + abs(rng.gauss(0.0, vol * 0.45)))), 2)
                low_px = round(max(band.limit_down, min(open_px, close_px) * (1.0 - abs(rng.gauss(0.0, vol * 0.45)))), 2)
                band_final = compute_cn_price_limits(prev_close, close_px, limit_pct)
                nb_flow = rng.gauss(1.2e8 if close_px >= prev_close else -0.9e8, 3.8e8)
                nb_shares = max(1e6, nb_shares + nb_flow / max(close_px, 1.0))
                shares_out = item["microstructure_meta"]["shares_outstanding"]
                cn_micro_rows.append(
                    (
                        iid,
                        d,
                        round(prev_close, 2),
                        band_final.limit_up,
                        band_final.limit_down,
                        band_final.hit_limit_up,
                        band_final.hit_limit_down,
                        bool(item["microstructure_meta"].get("is_st", False)),
                        round(max(0.15, abs(rng.gauss(1.3, 0.7))), 2),
                        round(nb_shares, 0),
                        round((nb_shares / shares_out) * 100.0, 2),
                        round(nb_flow, 2),
                        round(shares_out * close_px * 0.018, 2),
                    )
                )
            else:
                close_px = round(raw_close, 2 if raw_close >= 10 else 4)
                open_px = round(prev_close * (1.0 + rng.gauss(0.0, vol * 0.3)), 2)
                high_px = round(max(open_px, close_px) * (1.0 + abs(rng.gauss(0.0, vol * 0.5))), 2)
                low_px = round(min(open_px, close_px) * (1.0 - abs(rng.gauss(0.0, vol * 0.5))), 2)

            volume = round(base_vol * max(0.35, 1.0 + rng.gauss(0.0, 0.35) + abs(ret) * 12.0), 2)
            vwap = round((high_px + low_px + close_px) / 3.0, 2)
            ts = datetime(d.year, d.month, d.day, 0, 0, tzinfo=UTC)
            ohlcv_rows.append(
                (
                    iid,
                    "1d",
                    ts,
                    "CONTINUOUS_24_7" if mkt == "CRYPTO" else "REGULAR",
                    item["base_currency"],
                    open_px,
                    high_px,
                    low_px,
                    close_px,
                    close_px,
                    volume,
                    round(volume * vwap, 2),
                    vwap,
                    1.0,
                    "seed_institutional",
                )
            )

            if mkt == "CRYPTO":
                fr = round(0.0001 + ret * 0.004 + rng.gauss(0.0, 0.00006), 6)
                oi_usd = max(5e8, oi_usd * (1.0 + ret * 0.4 + rng.gauss(0.0, 0.015)))
                tvl_usd = max(0.0, tvl_usd * (1.0 + ret * 0.35)) if tvl_usd > 0 else 0.0
                cex_vol = volume * close_px * 0.82
                dex_vol = volume * close_px * (0.28 if "SOL" in iid else 0.18)
                basis_bps = round(fr * 10000.0 * 3.5 + rng.gauss(2.5, 4.0), 2)
                crypto_metric_rows.append(
                    (
                        iid,
                        ts,
                        "BINANCE" if "PERP" in iid else "AGG",
                        fr,
                        round(fr * 3.0 * 365.0 * 100.0, 2),
                        round(oi_usd, 2),
                        round(close_px * (1.0 + basis_bps / 10000.0), 2),
                        close_px,
                        basis_bps,
                        round(cex_vol, 2),
                        round(dex_vol, 2),
                        round(tvl_usd, 2),
                        (920_000 if "BTC" in iid else (540_000 if "ETH" in iid else 2_850_000)),
                    )
                )

            px = close_px
        latest_prices[iid] = px

    db.bulk_insert_polars(
        "fact_ohlcv",
        pl.DataFrame(
            ohlcv_rows,
            schema=[
                "instrument_id", "timeframe", "ts_utc", "session_type", "currency",
                "open", "high", "low", "close", "adj_close", "volume",
                "turnover_value", "vwap", "adj_factor", "source_adapter",
            ],
            orient="row",
        ),
    )
    db.bulk_insert_polars(
        "fact_cn_microstructure",
        pl.DataFrame(
            cn_micro_rows,
            schema=[
                "instrument_id", "trade_date", "prev_close", "limit_up_price", "limit_down_price",
                "hit_limit_up", "hit_limit_down", "is_st_flagged", "turnover_rate_pct",
                "northbound_hold_shares", "northbound_hold_pct", "northbound_net_flow_cny",
                "margin_buy_balance_cny",
            ],
            orient="row",
        ),
    )
    db.bulk_insert_polars(
        "fact_crypto_metrics",
        pl.DataFrame(
            crypto_metric_rows,
            schema=[
                "instrument_id", "ts_utc", "venue", "funding_rate", "annualized_funding_pct",
                "open_interest_usd", "mark_price", "index_price", "perp_basis_bps",
                "cex_volume_24h_usd", "dex_volume_24h_usd", "tvl_usd", "active_addresses_24h",
            ],
            orient="row",
        ),
    )

    # 4. Standardized Financials (Annual + Derived Quarterly)
    fin_rows: list[tuple[Any, ...]] = []
    profiles = _seed_financials_profiles()
    metric_spec = [
        ("IS", "revenue"),
        ("IS", "gross_profit"),
        ("IS", "ebitda"),
        ("IS", "ebit"),
        ("IS", "net_income"),
        ("BS", "total_assets"),
        ("BS", "total_debt"),
        ("BS", "cash_and_equiv"),
        ("BS", "total_equity"),
        ("CF", "operating_cf"),
        ("CF", "capex"),
    ]
    for iid, prof in profiles.items():
        std = prof["std"]
        ccy = prof["ccy"]
        shares = float(prof["shares"])
        prev_vals: dict[str, float] = {}

        for row in prof["annual"]:
            fy = row[0]
            vals = row[1:]
            fiscal_end = date(fy, 12, 31)
            filing_dt = date(fy + 1, 2, 20)
            ocf, capex = vals[9], vals[10]
            fcf = ocf - capex
            net_inc = vals[4]
            eps = net_inc / shares if shares > 0 else 0.0

            all_metrics = list(zip(metric_spec, vals, strict=True)) + [
                (("CF", "free_cash_flow"), fcf),
                (("IS", "eps_diluted"), round(eps, 4)),
                (("BS", "shares_diluted"), shares),
            ]
            for (stmt, code), val in all_metrics:
                yoy = None
                if code in prev_vals and abs(prev_vals[code]) > 1e-9:
                    yoy = round((val - prev_vals[code]) / abs(prev_vals[code]), 4)
                prev_vals[code] = val
                fin_rows.append(
                    (
                        iid,
                        stmt,
                        "FY",
                        fy,
                        fiscal_end,
                        filing_dt,
                        std,
                        ccy,
                        code,
                        float(val),
                        yoy,
                        None,
                        "seed_xbrl_cas",
                    )
                )

            # Generate realistic Q1-Q4 breakdown for the last 2 fiscal years
            if fy >= 2024:
                q_weights = [0.22, 0.24, 0.25, 0.29]
                q_ends = [date(fy, 3, 31), date(fy, 6, 30), date(fy, 9, 30), date(fy, 12, 31)]
                for qi, (qw, qend) in enumerate(zip(q_weights, q_ends, strict=True), start=1):
                    q_filing = qend + timedelta(days=38)
                    for (stmt, code), val in all_metrics:
                        q_val = val if stmt == "BS" else val * qw
                        fin_rows.append(
                            (
                                iid,
                                stmt,
                                f"Q{qi}",
                                fy,
                                qend,
                                q_filing,
                                std,
                                ccy,
                                code,
                                float(q_val),
                                round(rng.uniform(0.04, 0.28), 4),
                                round(rng.uniform(-0.04, 0.12), 4),
                                "seed_xbrl_cas",
                            )
                        )

    db.bulk_insert_polars(
        "fact_financials",
        pl.DataFrame(
            fin_rows,
            schema=[
                "instrument_id", "statement_type", "period_type", "fiscal_year",
                "fiscal_end_date", "filing_date", "accounting_standard", "reporting_currency",
                "metric_code", "value", "yoy_growth", "qoq_growth", "source_adapter",
            ],
            orient="row",
            infer_schema_length=None,
        ),
    )

    # 5. US Options Chains & 13F Institutional Holdings
    opt_rows: list[tuple[Any, ...]] = []
    h13f_rows: list[tuple[Any, ...]] = []
    exp_date = today + timedelta(days=35)
    for iid in ("EQ:US:AAPL", "EQ:US:NVDA", "EQ:US:MSFT"):
        spot = latest_prices[iid]
        sym = iid.split(":")[-1]
        step = 5.0 if spot > 100 else 2.5
        atm = round(spot / step) * step
        for offset in (-3, -2, -1, 0, 1, 2, 3):
            strike = round(atm + offset * step, 2)
            moneyness = (spot - strike) / spot
            iv = round(0.24 + abs(moneyness) * 0.45 + (0.14 if sym == "NVDA" else 0.0), 4)
            for opt_type in ("CALL", "PUT"):
                intrinsic = max(0.0, spot - strike) if opt_type == "CALL" else max(0.0, strike - spot)
                time_val = spot * iv * math.sqrt(35 / 365) * 0.38 * math.exp(-3.0 * moneyness * moneyness)
                mid = round(intrinsic + time_val, 2)
                delta = round(
                    max(0.05, min(0.95, 0.5 + moneyness * 3.5))
                    if opt_type == "CALL"
                    else -max(0.05, min(0.95, 0.5 - moneyness * 3.5)),
                    3,
                )
                opt_rows.append(
                    (
                        iid,
                        now_utc,
                        f"{sym}{exp_date.strftime('%y%m%d')}{opt_type[0]}{int(strike * 1000):08d}",
                        exp_date,
                        strike,
                        opt_type,
                        round(max(0.05, mid - 0.06), 2),
                        round(mid + 0.06, 2),
                        mid,
                        iv,
                        int(12000 + rng.randint(500, 48000)),
                        int(2500 + rng.randint(100, 18000)),
                        delta,
                        round(0.018 * math.exp(-4.0 * moneyness * moneyness), 4),
                        round(-mid / 55.0, 4),
                        round(spot * 0.0012, 4),
                    )
                )

        inst_holders = [
            ("0000102909", "Vanguard Group Inc.", 8.82, 14_200_000),
            ("0001364742", "BlackRock Inc.", 7.15, 9_850_000),
            ("0000093751", "State Street Corp.", 3.94, -2_100_000),
            ("0000315066", "FMR LLC (Fidelity)", 2.71, 6_400_000),
            ("0001067983", "Geode Capital Management", 2.18, 3_200_000),
        ]
        shares_out = next(i["microstructure_meta"]["shares_outstanding"] for i in INSTRUMENTS_SEED if i["instrument_id"] == iid)
        for cik, name, pct, qoq_chg in inst_holders:
            sh = int(shares_out * (pct / 100.0))
            h13f_rows.append(
                (iid, today - timedelta(days=45), today - timedelta(days=12), cik, name, sh, round(sh * spot, 2), pct, qoq_chg)
            )

    db.executemany(
        "INSERT OR REPLACE INTO fact_us_options VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        opt_rows,
    )
    db.executemany(
        "INSERT OR REPLACE INTO fact_us_13f_holdings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        h13f_rows,
    )

    # 6. Corporate & Protocol Events (Displayed as Overlays on GP Chart)
    event_seeds = [
        ("ev-aapl-1", "EQ:US:AAPL", today - timedelta(days=260), "EARNINGS", "Q1 FY26 Earnings Beat (EPS $2.42 vs $2.35)", {"eps_est": 2.35, "eps_act": 2.42}),
        ("ev-aapl-2", "EQ:US:AAPL", today - timedelta(days=170), "DIVIDEND", "Quarterly Cash Dividend $0.26/sh", {"div": 0.26}),
        ("ev-aapl-3", "EQ:US:AAPL", today - timedelta(days=85), "SEC_10K", "SEC Form 10-K Annual Filing Submitted", {"form": "10-K"}),
        ("ev-aapl-4", "EQ:US:AAPL", today - timedelta(days=28), "EARNINGS", "Q4 Earnings Release — Services Margin Record", {"eps_est": 1.68, "eps_act": 1.77}),
        ("ev-nvda-1", "EQ:US:NVDA", today - timedelta(days=210), "EARNINGS", "Blackwell Ramp Beats Data Center Consensus", {"eps_est": 0.85, "eps_act": 0.96}),
        ("ev-nvda-2", "EQ:US:NVDA", today - timedelta(days=115), "SEC_10Q", "SEC Form 10-Q Quarterly Report", {"form": "10-Q"}),
        ("ev-nvda-3", "EQ:US:NVDA", today - timedelta(days=22), "EARNINGS", "Data Center Revenue +78% YoY", {"eps_est": 1.12, "eps_act": 1.24}),
        ("ev-msft-1", "EQ:US:MSFT", today - timedelta(days=140), "DIVIDEND", "Quarterly Dividend Raised +10% to $0.83/sh", {"div": 0.83}),
        ("ev-msft-2", "EQ:US:MSFT", today - timedelta(days=34), "EARNINGS", "Azure AI Workload Growth Accelerates", {"eps_est": 3.18, "eps_act": 3.31}),
        ("ev-600519-1", "EQ:SSE:600519", today - timedelta(days=230), "CSRC_NOTICE", "SSE公告: 2025年度特别分红方案实施", {"div_cny": 23.88}),
        ("ev-600519-2", "EQ:SSE:600519", today - timedelta(days=125), "DIVIDEND", "派息除权除息日 ¥27.62/股", {"div_cny": 27.62}),
        ("ev-600519-3", "EQ:SSE:600519", today - timedelta(days=31), "EARNINGS", "三季报: 营收与归母净利稳健增长，直销占比提升", {"yoy_pct": 11.4}),
        ("ev-300750-1", "EQ:SZSE:300750", today - timedelta(days=165), "CSRC_NOTICE", "深交所公告: 神行超充电池海外工厂投产", {"board": "CHINEXT"}),
        ("ev-300750-2", "EQ:SZSE:300750", today - timedelta(days=35), "EARNINGS", "三季报超预期: 储能毛利率创新高", {"yoy_pct": 19.2}),
        ("ev-688981-1", "EQ:SSE:688981", today - timedelta(days=45), "EARNINGS", "科创板季报: 产能利用率回升至91%", {"util_pct": 91.0}),
        ("ev-btc-1", "CR:SPOT:BTC-USD", today - timedelta(days=290), "HALVING", "Post-Halving Supply Issuance Milestone (3.125 BTC/block)", {"reward": 3.125}),
        ("ev-btc-2", "CR:SPOT:BTC-USD", today - timedelta(days=62), "MACRO", "Global Spot Bitcoin ETF Cumulative Inflows Cross $65B", {"inflow_b": 65.0}),
        ("ev-eth-1", "CR:SPOT:ETH-USD", today - timedelta(days=180), "UPGRADE", "Ethereum Pectra Mainnet Upgrade Live (Blob Capacity 2x)", {"eip": "EIP-7702"}),
        ("ev-sol-1", "CR:SPOT:SOL-USD", today - timedelta(days=95), "UPGRADE", "Firedancer Validator Client Production Rollout", {"tps": 65000}),
    ]
    ev_rows = [
        (eid, iid, datetime(d.year, d.month, d.day, 14, 0, tzinfo=UTC), etype, title, json.dumps(payload), f"https://openterm.local/events/{eid}")
        for eid, iid, d, etype, title, payload in event_seeds
    ]
    db.executemany("INSERT OR REPLACE INTO fact_events VALUES (?, ?, ?, ?, ?, ?, ?)", ev_rows)

    # 7. Real-Time News & Filings Feed (EN + ZH with NLP Sentiment)
    raw_news = [
        ("n-01", 12, "SEC EDGAR / Reuters", "en", "NVIDIA Data Center Demand Surges as Hyperscalers Raise 2027 Capex Guidance", "Next-generation rack-scale AI clusters drive strong backlog visibility and record gross margin resilience.", ["EQ:US:NVDA", "EQ:US:MSFT"]),
        ("n-02", 28, "上交所公告 / 财联社", "zh", "贵州茅台发布三季度经营数据：直销渠道稳健增长，北向资金连续5日净流入", "公司公告称核心大单品飞天茅台批价平稳，叠加高比例分红回购计划，获外资机构持续增持。", ["EQ:SSE:600519"]),
        ("n-03", 45, "CoinDesk / On-Chain", "en", "Bitcoin Perpetual Funding Rates Normalize While Institutional Spot ETF Inflows Accelerate", "Binance and CME open interest expand steadily without excessive retail leverage; basis remains healthy.", ["CR:SPOT:BTC-USD", "CR:PERP:BINANCE:BTC-USDT"]),
        ("n-04", 70, "SEC EDGAR 8-K", "en", "Apple Expands $110B Share Buyback Authorization Following Record Services Revenue", "Recurring App Store and iCloud margins beat street consensus despite softer hardware replacement cycle in Europe.", ["EQ:US:AAPL"]),
        ("n-05", 95, "深交所互动易 / 证券时报", "zh", "宁德时代储能电池出货量突破新高，创业板成交额居首获北向资金净流入", "欧洲及中东大型储能项目陆续交付，叠加原材料成本下滑，毛利率持续改善超预期。", ["EQ:SZSE:300750"]),
        ("n-06", 130, "The Block / DefiLlama", "en", "Ethereum Layer-2 Settlement Volume Hits Record High; DEX Liquidity Deepens Across Uniswap", "Blob fee burn picks up as institutional RWA tokenization TVL crosses new milestone on Ethereum mainnet.", ["CR:SPOT:ETH-USD"]),
        ("n-07", 175, "Bloomberg Law / SEC", "en", "Regulators Review Cloud AI Infrastructure Concentration; Antitrust Probe Risk Weighs on Mega-Cap Tech", "Analysts note potential compliance investigation costs though enterprise cloud backlog remains resilient.", ["EQ:US:MSFT", "EQ:US:NVDA"]),
        ("n-08", 210, "科创板日报", "zh", "中芯国际晶圆代工产能利用率稳步回升，但成熟制程价格仍承压存在盈利风险", "本土汽车电子及消费芯片补库带动出货量增长，但高额资本开支折旧令短期利润承压。", ["EQ:SSE:688981"]),
        ("n-09", 260, "DeFi Research", "en", "Solana On-Chain DEX Volume Outperforms Peer L1s Amid Strong Stablecoin Inflows", "Daily active addresses and protocol fees reach multi-quarter highs with sub-second execution.", ["CR:SPOT:SOL-USD"]),
        ("n-10", 310, "北交所公告", "zh", "诺思兰德披露核心基因治疗临床进展公告，研发里程碑取得关键突破", "公司生物创新药项目完成重要阶段入组，北交所医药板块活跃度显著提升。", ["EQ:BSE:430047"]),
        ("n-11", 400, "Macro Desk", "en", "USD/CNY Stabilizes Near 7.20 as Cross-Border Stock Connect Flows Turn Net Positive", "Global multi-asset allocators rebalance across US tech, China A-share consumer leaders, and digital gold.", ["EQ:US:SPY", "EQ:SSE:600519", "CR:SPOT:BTC-USD"]),
    ]
    news_rows = []
    for nid, mins_ago, src, lang, title, summary, iids in raw_news:
        score, label = score_financial_sentiment(f"{title} {summary}", language=lang)
        news_rows.append(
            (
                nid,
                now_utc - timedelta(minutes=mins_ago),
                src,
                lang,
                title,
                summary,
                f"https://openterm.local/news/{nid}",
                iids,
                score,
                label,
                0.92,
            )
        )
    db.executemany(
        "INSERT OR REPLACE INTO fact_news_sentiment VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        news_rows,
    )

    # 8. Multi-Currency Sample Portfolio with T+1 China A-Share Lot
    db.execute(
        "INSERT OR REPLACE INTO dim_portfolios VALUES (?, ?, ?, ?, ?)",
        ["PORT_MAIN", "Global Multi-Asset Alpha", "USD", "EQ:US:SPY", now_utc],
    )
    tx_specs = [
        ("tx-1", "EQ:US:AAPL", today - timedelta(days=180), "BUY", 220.0, latest_prices["EQ:US:AAPL"] * 0.87, "USD", 1.0, "Core US Quality"),
        ("tx-2", "EQ:US:NVDA", today - timedelta(days=150), "BUY", 350.0, latest_prices["EQ:US:NVDA"] * 0.78, "USD", 1.0, "AI Compute Leader"),
        ("tx-3", "EQ:SSE:600519", today - timedelta(days=140), "BUY", 200.0, latest_prices["EQ:SSE:600519"] * 0.94, "CNY", 1.0 / 7.22, "A-Share Baijiu Core (Settled)"),
        ("tx-4", "EQ:SSE:600519", today, "BUY", 100.0, latest_prices["EQ:SSE:600519"], "CNY", 1.0 / usd_cny, "Intraday Add (T+1 Sell Locked Today)"),
        ("tx-5", "EQ:SZSE:300750", today - timedelta(days=110), "BUY", 1200.0, latest_prices["EQ:SZSE:300750"] * 0.86, "CNY", 1.0 / 7.24, "ChiNext EV Battery Leader"),
        ("tx-6", "CR:SPOT:BTC-USD", today - timedelta(days=170), "BUY", 0.85, latest_prices["CR:SPOT:BTC-USD"] * 0.76, "USD", 1.0, "Digital Macro Hedge"),
        ("tx-7", "CR:SPOT:ETH-USD", today - timedelta(days=130), "BUY", 14.0, latest_prices["CR:SPOT:ETH-USD"] * 0.89, "USD", 1.0, "L1 Settlement Allocation"),
    ]
    tx_rows = []
    for tx_id, iid, td, side, qty, price, ccy, fx_to_usd, notes in tx_specs:
        rule = next(i["settlement_rule"] for i in INSTRUMENTS_SEED if i["instrument_id"] == iid)
        settle_dt = compute_settlement_date(td, rule)
        tx_rows.append(
            (
                tx_id,
                "PORT_MAIN",
                iid,
                datetime(td.year, td.month, td.day, 10, 30, tzinfo=UTC),
                settle_dt,
                side,
                qty,
                round(price, 2),
                ccy,
                round(fx_to_usd, 6),
                round(qty * price * 0.0005, 2),
                notes,
            )
        )
    db.executemany(
        "INSERT OR REPLACE INTO fact_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tx_rows,
    )

    # Snapshot Parquet lakehouse for external analytics
    db.export_ohlcv_parquet()
