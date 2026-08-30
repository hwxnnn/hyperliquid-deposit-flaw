#!/usr/bin/env python3
"""
feeless-order.py — interactive tool for placing feeless (0% card fee) crypto
orders on Swapped.com using Hyperliquid's merchant on-ramp configuration.

Hyperliquid's app signs its Swapped widget URLs client-side with the merchant
keys published in its JS bundle (app.hyperliquid.xyz/assets/config-*.js), so
the signing is fully reproducible offline. This tool walks you through picking
a crypto + network, an amount and a destination address, then builds and signs
the widget URL exactly like the app does. Open the URL in a browser to place
the order; payment, KYC and delivery are handled by Swapped.com itself.

Usage:
    python3 feeless-order.py

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
# ----------------------------------------------------------------------------

# crypto -> {network label: Swapped currencyCode}
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
    "usdt_avalanche": r"0x[0-0a-fA-F]{40}",
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


def build_signed_url(address: str, currency_code: str, amount: str,
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


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def ask_amount() -> str:
    while True:
        raw = ask("Amount to spend (USD)", "100")
        if re.fullmatch(r"\d+(\.\d+)?", raw):
            return raw
        print("  Please enter a number, e.g. 100 or 250.50")


def choose_crypto() -> tuple[str, str]:
    options = list(NETWORKS)
    print("\nSelect crypto:")
    for i, name in enumerate(options, 1):
        print(f"  {i}) {name}")
    print(f"  {len(options) + 1}) Other (custom Swapped currencyCode)")
    while True:
        pick = ask("Choice", "1")
        if pick.isdigit() and 1 <= int(pick) <= len(options):
            crypto = options[int(pick) - 1]
            return crypto, choose_network(crypto)
        if pick.isdigit() and int(pick) == len(options) + 1:
            return "custom", ask("Swapped currencyCode (e.g. usdc_solana)")
        print(f"  Enter a number between 1 and {len(options) + 1}.")


def choose_network(crypto: str) -> str:
    networks = NETWORKS[crypto]
    labels = list(networks)
    print(f"\nSelect {crypto} network:")
    for i, label in enumerate(labels, 1):
        print(f"  {i}) {label}  ({networks[label]})")
    while True:
        pick = ask("Choice", "1")
        if pick.isdigit() and 1 <= int(pick) <= len(labels):
            return networks[labels[int(pick) - 1]]
        print(f"  Enter a number between 1 and {len(labels)}.")


def ask_address(currency_code: str) -> str:
    pattern = ADDRESS_PATTERNS.get(currency_code)
    while True:
        address = ask("Destination wallet address")
        if not address:
            print("  Address cannot be empty.")
            continue
        if pattern and not re.fullmatch(pattern, address):
            again = ask(
                f"  That doesn't look like a {currency_code} address. Use anyway? (y/N)"
            ).lower()
            if again in ("y", "yes"):
                return address
            continue
        return address


def main() -> int:
    print("=" * 62)
    print("Feeless Order — Swapped.com widget signer")
    print("(Hyperliquid merchant terms: Card 0% Fee / best rate)")
    print("=" * 62)

    while True:
        crypto, currency_code = choose_crypto()
        amount = ask_amount()
        address = ask_address(currency_code)

        url = build_signed_url(address, currency_code, amount)

        print("\n" + "-" * 62)
        print(f"  Crypto / network : {crypto} — {currency_code}")
        print(f"  Amount           : ${amount}")
        print(f"  Deliver to       : {address}")
        print("-" * 62)
        print("\nSigned widget URL:")
        print(f"  {url}")
        print("-" * 62)

        if ask("\nOpen in browser now? (y/N)").lower() in ("y", "yes"):
            opened = webbrowser.open(url)
            print("  Opened in your default browser." if opened
                  else "  Could not launch a browser — copy the URL above.")

        if ask("\nPlace another order? (y/N)").lower() not in ("y", "yes"):
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print()
        return_code = 130
        sys.exit(return_code)
