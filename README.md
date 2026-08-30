# hyperliquid-deposit-flaw

CLI tool for placing **feeless (0% card fee) crypto orders** on
[Swapped.com](https://swapped.com) using Hyperliquid's merchant on-ramp
configuration.

Hyperliquid's app offers "Buy USDC with Fiat" — a Swapped.com widget embedded
in the deposit modal. Swapped normally charges a card fee (~1.75% on direct
orders), but Hyperliquid's merchant integration is configured for **Card 0%
Fee / "best rate"**. This tool reproduces Hyperliquid's widget-URL signing so
you can open the same feeless widget directly, pointed at **any destination
address and amount** you choose — no Hyperliquid account, session, or login
required.

The tool is fully offline: it signs the widget URL locally and prints it. You
open the URL in a browser to place the order; payment, KYC and crypto delivery
are handled by Swapped.com itself.

## How it works

Hyperliquid's frontend signs its Swapped widget URLs **client-side**. The
merchant keys it uses are published in its public JS bundle
(`app.hyperliquid.xyz/assets/config-*.js`):

```js
{
  url: 'https://widget.swapped.com',
  publicKey: 'pk_live_f40e8c2087cc984d2eff84574604b7f7',
  secretKey: 'sk_live_a243d47bf0db6dbd4f6b8f6e9f5d9d1c',
  currencyCode: 'USDC_HYPERCORE'
}
```

The widget URL carries `apiKey`, `currencyCode`, `quoteCurrencyAmount` and
`walletAddress`, and Swapped validates it with an HMAC `signature` appended to
the query string. The signature is:

```
base64( HMAC-SHA256( secretKey, "?" + query-string ) )
```

i.e. an HMAC-SHA256 over the URL's search string (leading `?` included,
parameters in the order above), base64-encoded, then URL-encoded — exactly what
the Hyperliquid app computes in the browser with WebCrypto. This tool performs
the same computation with `openssl`.

Since the signing key is public, the signature — and therefore the feeless
merchant terms — are reproducible by anyone, for any destination address.

## Usage

```bash
./feeless-order.sh "<DESTINATION_WALLET_ADDRESS>"
```

Example (USDC to a Hyperliquid/HyperCore address):

```bash
./feeless-order.sh "0x1234567890AbCdEf1234567890aBcDeF12345678"
```

Output:

```
Destination address:  0x1234567890AbCdEf1234567890aBcDeF12345678
Currency code:        USDC_HYPERCORE
Amount:               100

Signed widget URL (feeless order):
  https://widget.swapped.com/?apiKey=pk_live_...&currencyCode=USDC_HYPERCORE&quoteCurrencyAmount=100&walletAddress=0x1234...&signature=...

Open it in a browser to load the Swapped widget with Hyperliquid's merchant
terms (Card 0% Fee / best rate) for the address above.
```

Open the printed URL in a browser: the Swapped widget loads with the quote
pre-filled, "Card 0% Fee", and the "Buy USDC via Card" button enabled — pointed
at your chosen address.

### Options

| Option | Default | Purpose |
|---|---|---|
| `--amount=<n>` | `100` | Fiat amount for the quote |
| `--currency-code=<code>` | `USDC_HYPERCORE` | Swapped currencyCode — the network the crypto is delivered on |
| `--api-key=<key>` | `pk_live_f40e...` (bundle value) | Override merchant publishable key |
| `--secret-key=<key>` | `sk_live_a243...` (bundle value) | Override merchant signing key |

Env-var equivalents: `AMOUNT`, `CURRENCY_CODE`, `SWAPPED_APIKEY`,
`SWAPPED_SECRETKEY`, `SWAPPED_URL`.

### Other networks

`--currency-code` accepts any Swapped currency code, e.g.:

```bash
./feeless-order.sh --currency-code=USDC_SOLANA --amount=500 "<SOLANA_ADDRESS>"
```

The destination address must be valid for the network encoded in the code
(`USDC_HYPERCORE` expects a `0x`-style Hyperliquid address, `USDC_SOLANA` a
base58 Solana address, etc.). See Swapped's supported-cryptocurrencies docs
for the full code list.

## Requirements

- `bash`, `openssl`, `base64` (all standard on macOS/Linux)
- No network access, account, or authentication needed to generate the URL

## Verification

To confirm the tool signs identically to the real app: open
[app.hyperliquid.xyz](https://app.hyperliquid.xyz) → **Deposit** → **Buy USDC
with Fiat**, copy the `widget.swapped.com` iframe URL, and run the tool with
the same address and `--amount=100`. The `signature` values match
byte-for-byte.

## Notes

- The widget validates the `signature` over the full query string: any
  hand-edit of `walletAddress` or `quoteCurrencyAmount` without re-signing
  makes Swapped reject the URL and reset the widget to its default
  (fee-charging) state. The tool re-signs properly, so its URLs are accepted.
- The merchant keys above are publishable in the sense that Hyperliquid ships
  them to every visitor of its app; if they rotate, point the overrides at the
  current `config-*.js` bundle values.
- This tool only generates widget URLs. It does not submit payments, hold
  funds, or interact with Hyperliquid.
