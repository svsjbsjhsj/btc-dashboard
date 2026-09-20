"""
strategy.py
منطق استراتيجية "LS_ratio contrarian" - مُختبر ومؤكد بـ walk-forward.
"""

import pandas as pd
import numpy as np

# البارامترات المعتمدة (النسخة "الأصلية"، بلا هدف ربح ثابت)
Z_THRESHOLD = 0.5
STOP_ATR_MULT = 3.0
TARGET_DAILY_VOL = 0.005
MAX_LEVERAGE = 1.0
MAX_DRAWDOWN_PCT = 15.0
DD_PAUSE_DAYS = 7


def compute_signal(df: pd.DataFrame) -> pd.DataFrame:
    """
    df: DataFrame فيه أعمدة: date, close, high, low, longShortRatio
    مرتب تصاعدياً بالتاريخ، آخر 60+ يوم على الأقل
    """
    df = df.copy()
    df["ret1"] = df["close"].pct_change()
    df["LS_z"] = (
        (df["longShortRatio"] - df["longShortRatio"].rolling(60).mean())
        / df["longShortRatio"].rolling(60).std()
    )
    df["prev_close"] = df["close"].shift(1)
    df["tr"] = df[["high", "prev_close"]].max(axis=1) - df[["low", "prev_close"]].min(axis=1)
    df["atr14"] = df["tr"].rolling(14).mean()
    df["vol20"] = df["ret1"].rolling(20).std()
    return df


def classify_signal(z: float) -> str:
    """يحول z-score لإشارة BUY/SELL/FLAT."""
    if pd.isna(z):
        return "FLAT"
    if z > Z_THRESHOLD:
        return "SELL"
    elif z < -Z_THRESHOLD:
        return "BUY"
    else:
        return "FLAT"


def get_today_signal(df: pd.DataFrame) -> dict:
    """
    يرجع dict فيه معلومات إشارة آخر يوم:
    date, signal, price, z_score
    """
    last = df.iloc[-1]
    z = last["LS_z"]
    signal = classify_signal(z)
    return {
        "date": last["date"],
        "signal": signal,
        "price": float(last["close"]),
        "z_score": float(z) if not pd.isna(z) else None,
    }
