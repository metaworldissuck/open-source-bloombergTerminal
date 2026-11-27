from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.security_master import SecurityMaster

MARKET_CODES = {"US", "CH", "CN", "SS", "SZ", "BJ", "HK"}
ASSET_KEY_MAP = {
    "<EQUITY>": "EQUITY",
    "EQUITY": "EQUITY",
    "EQ": "EQUITY",
    "<CRYPTO>": "CRYPTO",
    "CRYPTO": "CRYPTO",
    "CR": "CRYPTO",
    "<FX>": "FX",
    "FX": "FX",
    "<INDEX>": "INDEX",
    "INDEX": "INDEX",
}
SECURITY_FUNCTIONS = {
    "DES": "Security Description & Microstructure",
    "FA": "Financial Analysis & DCF Valuation",
    "GP": "Graph Price & Technicals",
    "COMP": "Cross-Market Peer Comparison",
    "OPT": "US Options Chain, IV Skew & SEC 13F",
    "PERP": "Crypto Perpetual Funding, OI & CEX/DEX",
    "NEWS": "Real-Time News, Filings & Sentiment",
}
GLOBAL_FUNCTIONS = {
    "NEWS": "Global News, Filings & Sentiment Feed",
    "FLOW": "China A-Share Northbound/Southbound & 涨跌停 Monitor",
    "PERP": "Crypto Perpetual Funding, OI & On-Chain TVL",
    "OPT": "US Options Chain & SEC 13F Monitor",
    "PORT": "Multi-Currency Portfolio & Risk Analytics",
    "BQL": "Programmable SQL/Python Quant Console",
    "COMP": "Cross-Market Peer Comparison",
    "HELP": "Mnemonic Command Reference",
}
ALL_FUNCTIONS = {**SECURITY_FUNCTIONS, **GLOBAL_FUNCTIONS}
TIMEFRAME_TOKENS = {"1M", "5M", "15M", "1H", "4H", "1D", "1W", "1MO", "3M", "6M", "1Y", "2Y", "ALL"}


@dataclass
class ParsedCommand:
    raw: str
    function: str
    instrument_ids: list[str] = field(default_factory=list)
    instruments: list[dict[str, Any]] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    is_global: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "function": self.function,
            "instrument_ids": self.instrument_ids,
            "instruments": self.instruments,
            "args": self.args,
            "is_global": self.is_global,
            "error": self.error,
        }


class MnemonicCommandParser:
    """Deterministic Bloomberg-style mnemonic command lexer & parser.

    Supports:
    - Full syntax:        'AAPL US <Equity> DES', '600519 CH <Equity> FA', 'BTC-USD <Crypto> GP 1D'
    - Shorthand syntax:   '600519 FA', 'NVDA GP 1Y', 'BTC DES'
    - Context-inherited:  'FA', 'GP', 'DES' (uses active_instrument_id)
    - Multi-security:     'AAPL US, NVDA US, 600519 CH COMP'
    - Global functions:   'PORT', 'BQL', 'NEWS', 'NEWS AAPL'
    """

    def __init__(self, security_master: SecurityMaster):
        self.sm = security_master

    def parse(self, raw_input: str, active_instrument_id: str | None = None) -> ParsedCommand:
        cleaned = " ".join(raw_input.strip().split())
        if not cleaned:
            return ParsedCommand(raw=raw_input, function="", error="Empty command")

        # Handle multi-security comma-separated list (e.g. "AAPL US, MSFT US, 600519 CH COMP")
        if "," in cleaned:
            return self._parse_multi_security(cleaned)

        tokens = cleaned.split(" ")
        upper_tokens = [t.upper() for t in tokens]

        # Case 1: Leading global function (e.g., "PORT", "BQL", "NEWS", "NEWS AAPL", "HELP")
        if upper_tokens[0] in GLOBAL_FUNCTIONS and (
            len(upper_tokens) == 1 or upper_tokens[0] in ("PORT", "BQL", "NEWS", "HELP")
        ):
            fn = upper_tokens[0]
            rest = tokens[1:]
            instruments: list[dict[str, Any]] = []
            args: list[str] = []
            if fn == "NEWS" and rest:
                resolved = self.sm.resolve(rest[0])
                if resolved:
                    instruments.append(resolved)
                    args = rest[1:]
                else:
                    args = rest
            else:
                args = rest
            return ParsedCommand(
                raw=raw_input,
                function=fn,
                instrument_ids=[i["instrument_id"] for i in instruments],
                instruments=instruments,
                args=args,
                is_global=len(instruments) == 0,
            )

        # Case 2: Context-inherited function switch (e.g., user types "FA" or "GP 1Y")
        if upper_tokens[0] in SECURITY_FUNCTIONS:
            fn = upper_tokens[0]
            args = upper_tokens[1:]
            instruments = []
            if active_instrument_id:
                resolved = self.sm.resolve(active_instrument_id)
                if resolved:
                    instruments.append(resolved)
            if not instruments and fn not in GLOBAL_FUNCTIONS:
                return ParsedCommand(
                    raw=raw_input,
                    function=fn,
                    args=args,
                    error=f"Function '{fn}' requires an active security (e.g., AAPL US <Equity> {fn})",
                )
            return ParsedCommand(
                raw=raw_input,
                function=fn,
                instrument_ids=[i["instrument_id"] for i in instruments],
                instruments=instruments,
                args=args,
                is_global=len(instruments) == 0,
            )

        # Case 3: Security-first syntax: <TICKER> [MARKET] [<AssetKey>] [FUNCTION] [ARGS...]
        fn_idx: int | None = None
        for idx, tok in enumerate(upper_tokens):
            if tok in ALL_FUNCTIONS and idx >= 1:
                fn_idx = idx
                break

        sec_tokens = upper_tokens[:fn_idx] if fn_idx is not None else upper_tokens
        fn = upper_tokens[fn_idx] if fn_idx is not None else "DES"
        args = upper_tokens[fn_idx + 1 :] if fn_idx is not None else []

        # Strip optional trailing timeframe args if no explicit function was given (e.g. "BTC-USD 4H")
        if fn_idx is None and len(sec_tokens) >= 2 and sec_tokens[-1] in TIMEFRAME_TOKENS:
            args = [sec_tokens[-1]]
            sec_tokens = sec_tokens[:-1]
            fn = "GP"

        resolved = self._resolve_security_tokens(sec_tokens)
        if not resolved:
            return ParsedCommand(
                raw=raw_input,
                function=fn,
                args=args,
                error=f"Unknown security: '{' '.join(sec_tokens)}'. Try AAPL US, 600519 CH, or BTC-USD.",
            )

        return ParsedCommand(
            raw=raw_input,
            function=fn,
            instrument_ids=[resolved["instrument_id"]],
            instruments=[resolved],
            args=args,
            is_global=False,
        )

    def _parse_multi_security(self, cleaned: str) -> ParsedCommand:
        # Extract trailing function name if present on the final comma segment
        segments = [seg.strip() for seg in cleaned.split(",") if seg.strip()]
        fn = "COMP"
        args: list[str] = []

        last_tokens = segments[-1].split()
        for idx, tok in enumerate(last_tokens):
            if tok.upper() in ALL_FUNCTIONS:
                fn = tok.upper()
                args = [t.upper() for t in last_tokens[idx + 1 :]]
                segments[-1] = " ".join(last_tokens[:idx]).strip()
                break

        instruments: list[dict[str, Any]] = []
        for seg in segments:
            if not seg:
                continue
            resolved = self._resolve_security_tokens([t.upper() for t in seg.split()])
            if resolved:
                instruments.append(resolved)

        if not instruments:
            return ParsedCommand(
                raw=cleaned,
                function=fn,
                error="Could not resolve any tickers in comparison list.",
            )

        return ParsedCommand(
            raw=cleaned,
            function=fn,
            instrument_ids=[i["instrument_id"] for i in instruments],
            instruments=instruments,
            args=args,
            is_global=False,
        )

    def _resolve_security_tokens(self, tokens: list[str]) -> dict[str, Any] | None:
        if not tokens:
            return None
        asset_hint: str | None = None
        market_hint: str | None = None
        core_tokens: list[str] = []

        for tok in tokens:
            if tok in ASSET_KEY_MAP:
                asset_hint = ASSET_KEY_MAP[tok]
            elif tok in MARKET_CODES and core_tokens:
                market_hint = tok
            else:
                core_tokens.append(tok)

        if not core_tokens:
            return None
        raw_symbol = core_tokens[0]
        return self.sm.resolve(raw_symbol, market_hint=market_hint, asset_hint=asset_hint)

    def autocomplete(self, prefix: str, active_instrument_id: str | None = None) -> list[dict[str, Any]]:
        """Return context-aware Bloomberg command suggestions for the global command bar."""
        q = prefix.strip()
        q_up = q.upper()
        suggestions: list[dict[str, Any]] = []

        # Suggest matching functions first if query is empty or matches a function code
        for code, desc in ALL_FUNCTIONS.items():
            if not q_up or code.startswith(q_up):
                suggestions.append(
                    {
                        "kind": "FUNCTION",
                        "label": code,
                        "detail": desc,
                        "insert_text": code,
                        "badge": "GLOBAL" if code in GLOBAL_FUNCTIONS else "FUNC",
                    }
                )

        # Check if user already typed a security and is now typing a function (e.g. "600519 CH ")
        tokens = re.split(r"\s+", q)
        if len(tokens) >= 2 and prefix.endswith(" "):
            resolved = self._resolve_security_tokens([t.upper() for t in tokens if t])
            if resolved:
                base_cmd = q.strip()
                fn_suggestions = [
                    {
                        "kind": "COMMAND",
                        "label": f"{base_cmd} {fn}",
                        "detail": f"{resolved['display_name']} — {desc}",
                        "insert_text": f"{base_cmd} {fn}",
                        "badge": resolved["market"],
                    }
                    for fn, desc in SECURITY_FUNCTIONS.items()
                ]
                return fn_suggestions

        # Fuzzy search securities
        sec_query = tokens[0] if tokens else ""
        sec_matches = self.sm.search(sec_query, limit=8)
        for item in sec_matches:
            if item["market"] == "US":
                cmd_prefix = f"{item['native_symbol']} US <Equity>"
            elif item["market"] == "CN_ASHARE":
                cmd_prefix = f"{item['native_symbol']} CH <Equity>"
            else:
                cmd_prefix = f"{item['native_symbol']} <Crypto>"
            local = f" ({item['display_name_local']})" if item.get("display_name_local") else ""
            suggestions.append(
                {
                    "kind": "SECURITY",
                    "label": f"{cmd_prefix} DES",
                    "detail": f"{item['display_name']}{local} [{item['instrument_id']}]",
                    "insert_text": f"{cmd_prefix} DES",
                    "badge": item["market"],
                    "instrument_id": item["instrument_id"],
                }
            )

        return suggestions[:12]
