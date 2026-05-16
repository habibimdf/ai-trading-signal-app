from __future__ import annotations


def normalize_pair(pair: str) -> str:
    return pair.replace("/", "_").replace("-", "_").upper()


def pip_size(pair: str) -> float:
    pair = normalize_pair(pair)
    if pair.endswith("JPY"):
        return 0.01
    if pair in ["XAU_USD", "BTC_USDT"]:
        return 0.01
    return 0.0001


def money_balance_to_usd(balance: float, account_type: str) -> float:
    """If USC/cent account, 100 USC = 1 USD."""
    return balance / 100 if account_type.upper() == "USC" else balance


def pip_value_per_standard_lot(pair: str, price: float) -> float:
    """
    Approximation for educational signal sizing.
    - EUR_USD/GBP_USD: about $10 per pip per standard lot.
    - USD_JPY: pip value = 1000 JPY / current price.
    - XAU_USD: many brokers use 100 oz/lot, 0.01 move ≈ $1/lot.
    Always verify with your broker's contract specification.
    """
    pair = normalize_pair(pair)
    if pair == "BTC_USDT":
        return 0.01
    if pair == "XAU_USD":
        return 1.0
    if pair == "USD_JPY":
        return 1000 / price if price else 6.7
    return 10.0


def calculate_lot_size(pair: str, entry: float, stop_loss: float, balance: float, account_type: str, risk_percent: float) -> dict:
    balance_usd = money_balance_to_usd(balance, account_type)
    risk_amount_usd = balance_usd * (risk_percent / 100)
    distance = abs(entry - stop_loss)
    if distance <= 0:
        return {"lot_size": 0.0, "risk_amount_usd": risk_amount_usd, "sl_pips": 0.0}

    pips = distance / pip_size(pair)
    pip_value = pip_value_per_standard_lot(pair, entry)
    lot = risk_amount_usd / (pips * pip_value) if pips * pip_value > 0 else 0

    # Round down a little to avoid over-risking.
    return {
        "lot_size": round(max(lot, 0), 3),
        "risk_amount_usd": round(risk_amount_usd, 2),
        "sl_pips": round(pips, 1),
    }
