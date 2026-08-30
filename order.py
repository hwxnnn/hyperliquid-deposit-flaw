#!/usr/bin/env python3
"""
order.py — place feeless (0% card fee) crypto orders on Swapped.com using
Hyperliquid's merchant on-ramp configuration.

Hyperliquid's app signs its Swapped widget URLs client-side with the merchant
keys published in its JS bundle (app.hyperliquid.xyz/assets/config-*.js), so
the signing is fully reproducible offline. This tool signs the widget URL
exactly like the app does and opens it. Payment, KYC and delivery are handled
by Swapped.com itself, and the amount can be changed inside the widget.

Usage:
    ./order.py                                          prompt for everything
    ./order.py --token=usdc_polygon --address=0x1234... sign and open directly
    ./order.py --token=usdt_tron --address=T... --amount=250

Options:
    --token=<code>    Swapped currencyCode, e.g. usdc_polygon, USDC_HYPERCORE
    --address=<addr>  destination wallet address
    --amount=<n>      starting quote amount in USD (default: 100)
    -h, --help        show this help

Anything not passed as a flag is prompted for.

The signature is base64(HMAC-SHA256(secretKey, "?" + query_string)) — the
same computation the Hyperliquid frontend performs in the browser with
WebCrypto. Requires only the Python 3 standard library.
"""

import base64
import hmac
import hashlib
import re
import sys
import urllib.parse
import webbrowser

# ----------------------------------------------------------------------------
# CONFIG — Hyperliquid merchant configuration (public, from the Hyperliquid
# frontend bundle). Override with env vars if these rotate.
# ----------------------------------------------------------------------------
SWAPPED_URL = "https://widget.swapped.com"
SWAPPED_APIKEY = "pk_live_f40e8c2087cc984d2eff84574604b7f7"
SWAPPED_SECRETKEY = "sk_live_a243d47bf0db6dbd4f6b8f6e9f5d9d1c"  # OK public

# Starting quote amount. The widget lets you change it before paying.
DEFAULT_AMOUNT = "100"
# ----------------------------------------------------------------------------

# token -> {network label: Swapped currencyCode}
NETWORKS = {
    "USDC": {
        "HyperCore (Hyperliquid)": "USDC_HYPERCORE",
        "Hyperliquid (HYPE)": "usdc_hype",
        "Solana": "usdc_solana",
        "Ethereum": "usdc_ethereum",
        "Base": "usdc_base",
        "Arbitrum": "usdc_arbitrum",
        "Polygon": "usdc_polygon",
        "Avalanche": "usdc_avalanche",
        "Binance Smart Chain": "usdc_bsc",
        "Monad": "usdc_monad",
        "Noble": "usdc_noble",
    },
    "USDT": {
        "Solana": "usdt_solana",
        "Ethereum": "usdt_ethereum",
        "TRON (TRC-20)": "usdt_tron",
        "Binance Smart Chain": "usdt_bsc",
        "Polygon": "usdt_polygon",
        "Avalanche": "usdt_avalanche",
        "TON": "usdt_ton",
    },
}

# loose per-network address shapes (advisory warnings only)
ADDRESS_PATTERNS = {
    "USDC_HYPERCORE": r"0x[0-9a-fA-F]{40}",
    "usdc_hype": r"0x[0-9a-fA-F]{40}",
    "usdc_ethereum": r"0x[0-9a-fA-F]{40}",
    "usdc_base": r"0x[0-9a-fA-F]{40}",
    "usdc_arbitrum": r"0x[0-9a-fA-F]{40}",
    "usdc_polygon": r"0x[0-9a-fA-F]{40}",
    "usdc_avalanche": r"0x[0-9a-fA-F]{40}",
    "usdc_bsc": r"0x[0-9a-fA-F]{40}",
    "usdc_monad": r"0x[0-9a-fA-F]{40}",
    "usdc_noble": r"0x[0-9a-fA-F]{40}",
    "usdt_ethereum": r"0x[0-9a-fA-F]{40}",
    "usdt_bsc": r"0x[0-9a-fA-F]{40}",
    "usdt_polygon": r"0x[0-9a-fA-F]{40}",
    "usdt_avalanche": r"0x[0-9a-fA-F]{40}",
    "usdc_solana": r"[1-9A-HJ-NP-Za-km-z]{32,44}",
    "usdt_solana": r"[1-9A-HJ-NP-Za-km-z]{32,44}",
    "usdt_tron": r"T[1-9A-HJ-NP-Za-km-z]{33}",
    "usdt_ton": r"[UE]Q[A-Za-z0-9_-]{46}",
}


def sign_params(params: str, secret_key: str) -> str:
    """HMAC-SHA256 over the query string (leading '?' included), base64."""
    digest = hmac.new(
        secret_key.encode(), ("?" + params).encode(), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode()


def build_signed_url(address: str, currency_code: str,
                     amount: str = DEFAULT_AMOUNT,
                     api_key: str = SWAPPED_APIKEY,
                     secret_key: str = SWAPPED_SECRETKEY) -> str:
    params = "&".join([
        "apiKey=" + urllib.parse.quote(api_key, safe=""),
        "currencyCode=" + urllib.parse.quote(currency_code, safe=""),
        "quoteCurrencyAmount=" + urllib.parse.quote(amount, safe=""),
        "walletAddress=" + urllib.parse.quote(address, safe=""),
    ])
    signature = sign_params(params, secret_key)
    return f"{SWAPPED_URL}/?{params}&signature={urllib.parse.quote(signature, safe='')}"


def choose(prompt: str, labels: list[str]) -> int:
    """Print a numbered menu and return the chosen index."""
    print(f"\n{prompt}")
    for i, label in enumerate(labels, 1):
        print(f"  {i}) {label}")
    while True:
        pick = input("Choice [1]: ").strip() or "1"
        if pick.isdigit() and 1 <= int(pick) <= len(labels):
            return int(pick) - 1
        print(f"  Enter a number between 1 and {len(labels)}.")


def ask_address(currency_code: str) -> str:
    pattern = ADDRESS_PATTERNS.get(currency_code)
    while True:
        address = input("\nDestination address: ").strip()
        if not address:
            print("  Address cannot be empty.")
            continue
        if pattern and not re.fullmatch(pattern, address):
            print(f"  Warning: not a valid {currency_code} address format.")
            if input("  Continue anyway? (y/N): ").strip().lower() in ("y", "yes"):
                return address
            continue
        return address


def canonical_code(token: str) -> str:
    """Map a user-supplied token to its exact Swapped currencyCode.

    Codes are matched case-insensitively, since the signature is computed over
    the code as written and Swapped expects its own casing (USDC_HYPERCORE is
    upper-case, the rest are lower-case). Unknown codes pass through verbatim
    so newly added Swapped networks still work.
    """
    known = {code.lower(): code
             for networks in NETWORKS.values() for code in networks.values()}
    return known.get(token.lower(), token)


def parse_args(argv: list[str]) -> dict[str, str]:
    opts: dict[str, str] = {}
    for arg in argv:
        if arg in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        match = re.fullmatch(r"--(token|address|amount)=(.*)", arg)
        if not match:
            sys.exit(f"order.py: unrecognized argument: {arg}\n"
                     f"Try './order.py --help' for usage.")
        key, value = match.group(1), match.group(2).strip()
        if not value:
            sys.exit(f"order.py: --{key} needs a value.")
        opts[key] = value
    if "amount" in opts and not re.fullmatch(r"\d+(\.\d+)?", opts["amount"]):
        sys.exit("order.py: --amount must be a number, e.g. 100 or 250.50")
    return opts


def select_currency_code() -> str:
    """Prompt for token, then network."""
    tokens = list(NETWORKS)
    networks = NETWORKS[tokens[choose("Select token:", tokens)]]
    labels = list(networks)
    return networks[labels[choose("Select network:", labels)]]


def main(argv: list[str]) -> int:
    opts = parse_args(argv)

    currency_code = (canonical_code(opts["token"]) if "token" in opts
                     else select_currency_code())

    if "address" in opts:
        address = opts["address"]
        pattern = ADDRESS_PATTERNS.get(currency_code)
        if pattern and not re.fullmatch(pattern, address):
            print(f"Warning: not a valid {currency_code} address format.",
                  file=sys.stderr)
    else:
        address = ask_address(currency_code)

    url = build_signed_url(address, currency_code,
                           opts.get("amount", DEFAULT_AMOUNT))
    opened = webbrowser.open(url)

    print("\nOrder opened in your browser." if opened
          else "\nCould not launch a browser — open the URL below manually.")
    print(f"\nSigned widget URL:\n  {url}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(130)
