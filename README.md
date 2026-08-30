# hyperliquid-deposit-flaw

Buy crypto with a card and pay **0% card fee**. Pay 100 USD, get 100 USDC.

## What this is

Normally, a [swapped.com](https://swapped.com) order through their website charges **1.75%** from you per order.

Hyperliquid has a deal with swapped.com. Inside the Hyperliquid app, the same buy box charges **0%**. Better rate too.

That deal is not locked to Hyperliquid. This tool makes the same 0% buy box link, but sent to **any wallet you want**, for **any amount**.

You do not need a Hyperliquid account. You do not need to log in.

## What it does

You run it. It prints a link. You open the link. swapped.com's buy box loads with 0% card fee, your amount, your wallet.

swapped.com handles the rest: your card, your ID check, sending you the coins. This tool never touches your info (other than the destination wallet address).

## Why it works

The Hyperliquid app builds that link in your own browser. To prove the link is real, it stamps it with a secret key.

But Hyperliquid ships that secret key to everybody. It sits in the app's public files (`app.hyperliquid.xyz/assets/config-*.js`):

```js
{
  url: 'https://widget.swapped.com',
  publicKey: 'pk_live_f40e8c2087cc984d2eff84574604b7f7',
  secretKey: 'sk_live_a243d47bf0db6dbd4f6b8f6e9f5d9d1c',
  currencyCode: 'USDC_HYPERCORE'
}
```

Anyone with that key can make the same stamp. So anyone can make the same 0% link.

The stamp is made like this:

```
base64( HMAC-SHA256( secretKey, "?" + query-string ) )
```

Same math the Hyperliquid app does.

## How to use it

### Answer three questions

```bash
./order.py
```

It asks which coin, which chain, and which wallet. Then it opens your link.

```
Select token:
  1) USDC
  2) USDT
Choice [1]: 1

Select network:
  1) HyperCore (Hyperliquid)
  2) Hyperliquid (HYPE)
  3) Solana
  ...
Choice [1]: 3

Destination address: 7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs

Order opened in your browser.

Signed widget URL:
  https://widget.swapped.com/?apiKey=...&currencyCode=usdc_solana&...&signature=...
```

### Or say it all in one line

```bash
./order.py --token=usdc_polygon --address="0x1234567890AbCdEf1234567890aBcDeF12345678"
```

No questions. It just opens your link and prints it.

Mix and match: give it only `--token` and it asks for the wallet. Give it neither and it asks for both.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `--token=<code>` | asks you | Which coin, and which chain it lands on |
| `--address=<addr>` | asks you | Where your coins go |
| `--amount=<n>` | `100` | How many dollars to start the quote at |
| `-y`, `--yes` | asks you | Skip the warning prompt |
| `-h`, `--help` | — | Show help |

You can change the amount inside the buy box before you pay, so `--amount` is only a starting number.

## It warns you every time

Before it makes any link, the tool stops and asks:

```
Warning: this tool signs an order with Hyperliquid's merchant
keys, on terms Hyperliquid did not extend to you. Doing so may
breach the terms of service of swapped.com, of Hyperliquid, or of
both.

swapped.com can tell these orders apart from ones the Hyperliquid
app made. Orders may be flagged, held, reversed or refused, and
accounts may be closed. Placing the order means handing swapped.com
your payment details and your identity documents.

You alone are responsible for any consequences of using this tool.

Continue? (y/N):
```

Say no and it quits. Say yes and it carries on. `--yes` skips the question.

Whatever happens next is on you.

### Non-HyperCore pairs get an extra line

Inside the Hyperliquid app, the only thing you can buy is **USDC on HyperCore**. That is the one order its 0% deal was ever meant to make.

So an order for any other coin or chain is plainly not something the Hyperliquid app could have made. The warning says so:

```
Hyperliquid only ever sells USDC on HyperCore (USDC_HYPERCORE). An
order for usdc_polygon is one its app could not have produced at all,
which makes this order especially easy to single out.
```

## Other chains

`--token` takes any Swapped coin code. Upper or lower case, either works.

```bash
./order.py --token=usdt_tron --address="<TRON_ADDRESS>" --amount=500
```

Your wallet must match the chain. `USDC_HYPERCORE` wants a `0x...` address. `usdc_solana` wants a Solana address. `usdt_tron` wants a `T...` address. If it looks wrong, the tool warns you first.

Codes it knows:

- **USDC** — `USDC_HYPERCORE`, `usdc_hype`, `usdc_solana`, `usdc_ethereum`, `usdc_base`, `usdc_arbitrum`, `usdc_polygon`, `usdc_avalanche`, `usdc_bsc`, `usdc_monad`, `usdc_noble`
- **USDT** — `usdt_solana`, `usdt_ethereum`, `usdt_tron`, `usdt_bsc`, `usdt_polygon`, `usdt_avalanche`, `usdt_ton`

Any other Swapped code works too — it gets passed straight through. Swapped's docs list them all.

## What you need

Python 3. Nothing to install.

No internet needed to make the link. No account. No login.

## Prove it yourself

Open [app.hyperliquid.xyz](https://app.hyperliquid.xyz) → **Deposit** → **Buy USDC with Fiat**. Copy the `widget.swapped.com` link out of the page. Run `./order.py --token=USDC_HYPERCORE --address=<same wallet>`.

The stamps match exactly. Same link, same terms.

## Things to know

- The stamp covers the whole link. Hand-edit the wallet or the amount and Swapped rejects it, then falls back to the normal fee. This tool re-stamps properly, so its links work.
- The keys above are not stolen. Hyperliquid hands them to every visitor. If they ever change them, grab the new ones from the `config-*.js` file and paste them at the top of `order.py`.
- This tool only makes links. It does not take payments, hold your coins, or touch Hyperliquid.
