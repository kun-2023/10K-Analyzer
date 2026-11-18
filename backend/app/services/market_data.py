from datetime import date, timedelta
from decimal import Decimal
from numbers import Real

import pandas as pd
import yfinance as yf

def get_latest_quote(symbol: str)->dict[str,str]|None:
    ticker=yf.Ticker(symbol.strip().upper())
    metadata=ticker.get_history_metadata()

    price=metadata.get("regularMarketPrice")
    quote_time=metadata.get("regularMarketTime")
    currency=metadata.get("currency")

    if price is None or quote_time is None or not currency:
        return None
    if isinstance(quote_time, Real):
        timestamp=pd.to_datetime(quote_time, unit='s', utc=True)
    else:
        timestamp=pd.to_datetime(quote_time, utc=True)
    if pd.isna(timestamp):
        return None

    return {
        "symbol": ticker.ticker,
        "price": str(Decimal(str(price))),
        "currency":currency,
        "as_of": timestamp.isoformat(),
        "source": "Yahoo Finance"
    }


def get_latest_close(symbol: str) -> dict[str, str] | None:
    ticker = yf.Ticker(symbol.strip().upper())
    history = ticker.history(
        period="5d",
        interval="1d",
        auto_adjust=False,
        actions=False,
        timeout=10,
    )
    if history.empty:
        return None

    closes = history["Close"].dropna().sort_index()
    if closes.empty:
        return None

    metadata = ticker.get_history_metadata()
    exchange_tz = metadata.get("exchangeTimezoneName")
    if not exchange_tz:
        return None

    now = pd.Timestamp.now(tz=exchange_tz)
    today = now.date()
    closes = closes[closes.index.date <= today]

    if not closes.empty and closes.index[-1].date() == today:
        regular_session = metadata.get("currentTradingPeriod", {}).get("regular", {})
        raw_end = regular_session.get("end")
        session_end = pd.to_datetime(
            raw_end,
            unit="s" if isinstance(raw_end, Real) else None,
            utc=True,
            errors="coerce",
        )

        if pd.notna(session_end):
            session_end = session_end.tz_convert(exchange_tz)

        if pd.isna(session_end) or session_end.date() != today or now < session_end:
            closes = closes[closes.index.date < today]

    if closes.empty:
        return None

    return {
        "trading_date": closes.index[-1].date().isoformat(),
        "price": str(Decimal(str(closes.iloc[-1]))),
    }

def get_valuation_price(symbol:str)->dict[str,str]|None:
    symbol=symbol.strip().upper()
    metadata=yf.Ticker(symbol).get_history_metadata()
    regular=metadata.get("currentTradingPeriod", {}).get("regular",{})
    now=pd.Timestamp.now(tz="UTC")

    def to_utc(value):
        if isinstance(value, Real):
            return pd.to_datetime(value, unit="s", utc=True)
        return pd.to_datetime(value, utc=True)
    session_start=to_utc(regular.get("start"))
    session_end=to_utc(regular.get("end"))

    if (
        pd.notna(session_start)
        and pd.notna(session_end)
        and session_start<=now<session_end
    ):
        quote=get_latest_quote(symbol)
        if quote:
            quote_time=to_utc(quote["as_of"])
            if (
                session_start<=quote_time<session_end
                and quote_time<=pd.Timestamp.now(tz="UTC")):
                return {**quote, "price_type":"regular_session_quote"}
    
    
    close=get_latest_close(symbol)
    currency=metadata.get("currency")
    if close is None or not currency:
        return None
    return {
        **close,
        "symbol": symbol,
        "currency": currency,
        "source": "Yahoo Finance",
        "price_type": "regular_session_close"
    }