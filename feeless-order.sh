#!/usr/bin/env bash
#
# feeless-order.sh — open feeless (0% card fee) crypto orders on Swapped.com
# using Hyperliquid's merchant on-ramp configuration.
#
# Hyperliquid's app embeds Swapped.com's buy widget for "Buy USDC with Fiat".
# The widget URL is signed client-side by the Hyperliquid frontend with the
# merchant HMAC key it ships in its public JS bundle, so the signing step is
# fully reproducible offline. This tool builds and signs a widget URL for any
# destination address and amount, exactly like the app does.
#
# Usage:
#   ./feeless-order.sh "<DESTINATION_WALLET_ADDRESS>"
#   ./feeless-order.sh --amount=250 "<DESTINATION_WALLET_ADDRESS>"
#   ./feeless-order.sh --currency-code=USDC_SOLANA --amount=500 "<SOLANA_ADDRESS>"
#
# The signed URL prints to stdout. Open it in a browser to load the Swapped
# widget with Hyperliquid's merchant terms (0% card fee / best rate).
# Payment, KYC and delivery are handled by Swapped.com itself.
#
# Options:
#   --amount=<n>            fiat amount for the quote (default: 100)
#   --currency-code=<code>  Swapped currencyCode (default: USDC_HYPERCORE)
#   --api-key=<key>         override the merchant publishable key
#   --secret-key=<key>      override the merchant signing key
#
# The destination address must be valid for the network encoded in the
# currencyCode (USDC_HYPERCORE expects a 0x-style Hyperliquid address).
#
# Requirements: bash, openssl, base64. No network access needed — the URL is
# signed locally, the widget only loads when you open it.

set -euo pipefail

# ============================================================================
# CONFIG — Hyperliquid merchant configuration (public, from the Hyperliquid
# frontend bundle: app.hyperliquid.xyz/assets/config-*.js). Override with
# --api-key / --secret-key if these rotate.
# ============================================================================
SWAPPED_URL="${SWAPPED_URL:-https://widget.swapped.com}"
SWAPPED_APIKEY="${SWAPPED_APIKEY:-pk_live_f40e8c2087cc984d2eff84574604b7f7}"
SWAPPED_SECRETKEY="${SWAPPED_SECRETKEY:-sk_live_a243d47bf0db6dbd4f6b8f6e9f5d9d1c}"
CURRENCY_CODE="${CURRENCY_CODE:-USDC_HYPERCORE}"
AMOUNT="${AMOUNT:-100}"
# ============================================================================

usage() {
  echo "usage: $0 [--amount=<n>] [--currency-code=<code>] \"<DESTINATION_WALLET_ADDRESS>\"" >&2
  echo "       --amount=<n>            fiat amount for the quote (default: 100)" >&2
  echo "       --currency-code=<code>  Swapped currencyCode (default: USDC_HYPERCORE)" >&2
  echo "       --api-key=<key>         override merchant publishable key" >&2
  echo "       --secret-key=<key>      override merchant signing key" >&2
  echo "       env equivalents: AMOUNT, CURRENCY_CODE, SWAPPED_APIKEY, SWAPPED_SECRETKEY, SWAPPED_URL" >&2
}

ADDRESS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --amount=*)
      AMOUNT="${1#*=}"; shift ;;
    --amount)
      [[ $# -lt 2 || -z "${2}" ]] && { echo "error: --amount requires a value." >&2; usage; exit 2; }
      AMOUNT="$2"; shift 2 ;;
    --currency-code=*|--currencyCode=*)
      CURRENCY_CODE="${1#*=}"; shift ;;
    --currency-code|--currencyCode)
      [[ $# -lt 2 || -z "${2}" ]] && { echo "error: --currency-code requires a value." >&2; usage; exit 2; }
      CURRENCY_CODE="$2"; shift 2 ;;
    --api-key=*)
      SWAPPED_APIKEY="${1#*=}"; shift ;;
    --secret-key=*)
      SWAPPED_SECRETKEY="${1#*=}"; shift ;;
    -h|--help)
      usage; exit 0 ;;
    --)
      shift; break ;;
    -*)
      echo "error: unknown option \"$1\"" >&2; usage; exit 2 ;;
    *)
      if [[ -z "${ADDRESS}" ]]; then
        ADDRESS="$1"
      else
        echo "error: unexpected extra argument \"$1\"" >&2; usage; exit 2
      fi
      shift ;;
  esac
done
# pick up an address that followed a bare `--`, if any
if [[ $# -gt 0 && -z "${ADDRESS}" ]]; then ADDRESS="$1"; fi

if [[ -z "${ADDRESS}" ]]; then
  echo "error: missing destination wallet address." >&2
  usage
  exit 2
fi

if ! [[ "${AMOUNT}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "error: --amount must be a number, got \"${AMOUNT}\"." >&2
  exit 2
fi

# ---- build the parameter string, in the exact order the widget validates ----
# The signature is an HMAC-SHA256 (base64) over the URL query string including
# the leading '?', keyed with the merchant secret — mirroring the Hyperliquid
# frontend's client-side signing (WebCrypto HMAC, `new URL(u).search`).
PARAMS="apiKey=${SWAPPED_APIKEY}&currencyCode=${CURRENCY_CODE}&quoteCurrencyAmount=${AMOUNT}&walletAddress=${ADDRESS}"
MESSAGE="?${PARAMS}"

# ---- sign locally with openssl ----------------------------------------------
SIGNATURE="$(printf '%s' "${MESSAGE}" | openssl dgst -sha256 -hmac "${SWAPPED_SECRETKEY}" -binary | base64)"

# encodeURIComponent() the base64 signature ('+', '/', '=')
SIGNATURE_ENC="$(printf '%s' "${SIGNATURE}" | sed -e 's/+/%2B/g' -e 's;/;%2F;g' -e 's/=/%3D/g')"

SIGNED_URL="${SWAPPED_URL}/?${PARAMS}&signature=${SIGNATURE_ENC}"

# ---- output -------------------------------------------------------------------
echo "Destination address:  ${ADDRESS}"
echo "Currency code:        ${CURRENCY_CODE}"
echo "Amount:               ${AMOUNT}"
echo
echo "Signed widget URL (feeless order):"
echo "  ${SIGNED_URL}"
echo
echo "Open it in a browser to load the Swapped widget with Hyperliquid's merchant"
echo "terms (Card 0% Fee / best rate) for the address above."
