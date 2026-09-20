"""
app.py
BTC LS_ratio Contrarian Dashboard - نقطة الدخول الرئيسية (Streamlit).
"""

import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_fetch import fetch_merged_data, DataFetchError
from strategy import compute_signal, get_today_signal, Z_THRESHOLD

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "signals_history.csv")

st.set_page_config(page_title="BTC LS_ratio Contrarian Dashboard", layout="wide")


# ---------- تخزين تاريخ الإشارات ----------

def load_history() -> pd.DataFrame:
    if os.path.exists(HISTORY_FILE):
        hist = pd.read_csv(HISTORY_FILE)
        hist["date"] = pd.to_datetime(hist["date"]).dt.date
        return hist
    return pd.DataFrame(columns=["date", "signal", "price", "z_score"])


def save_signal_if_new(hist: pd.DataFrame, today_signal: dict) -> pd.DataFrame:
    """يسجل إشارة اليوم إذا لم تكن مسجلة من قبل."""
    today_date = today_signal["date"]

    if not hist.empty and today_date in hist["date"].values:
        return hist  # مسجل مسبقاً، ما نزيدوش

    new_row = pd.DataFrame([today_signal])
    hist = pd.concat([hist, new_row], ignore_index=True)
    hist = hist.sort_values("date").reset_index(drop=True)
    hist.to_csv(HISTORY_FILE, index=False)
    return hist


# ---------- الواجهة ----------

st.title("📊 BTC LS_ratio Contrarian Dashboard")

with st.spinner("جاري تحميل بيانات BTC من Binance..."):
    try:
        df = fetch_merged_data(symbol="BTCUSDT", limit=500)
    except DataFetchError as e:
        st.error(str(e))
        st.stop()

if df.empty or len(df) < 60:
    st.warning("البيانات المُستلمة غير كافية لحساب الإشارة (يلزم 60+ يوم).")
    st.stop()

df = compute_signal(df)
today_signal = get_today_signal(df)

history = load_history()
history = save_signal_if_new(history, today_signal)

# ---------- لوحة الإحصائيات ----------

col1, col2, col3, col4 = st.columns(4)

signal_colors = {"BUY": "🟢", "SELL": "🔴", "FLAT": "⚪"}
last_hist_row = history.iloc[-1] if not history.empty else None

with col1:
    st.metric(
        "الإشارة الحالية",
        f"{signal_colors.get(today_signal['signal'], '')} {today_signal['signal']}",
    )
with col2:
    st.metric("السعر الحالي", f"${today_signal['price']:,.2f}")
with col3:
    z_display = f"{today_signal['z_score']:.2f}" if today_signal["z_score"] is not None else "N/A"
    st.metric("Z-score الحالي", z_display)
with col4:
    st.metric("عدد الإشارات المسجلة", len(history))

if last_hist_row is not None:
    st.caption(
        f"آخر إشارة مسجلة: **{last_hist_row['signal']}** بتاريخ "
        f"**{last_hist_row['date']}** (سعر ${last_hist_row['price']:,.2f})"
    )

if not history.empty:
    counts = history["signal"].value_counts()
    buy_n = int(counts.get("BUY", 0))
    sell_n = int(counts.get("SELL", 0))
    flat_n = int(counts.get("FLAT", 0))
    total_directional = buy_n + sell_n
    if total_directional > 0:
        st.caption(
            f"نسبة BUY: {buy_n / total_directional:.0%} | "
            f"نسبة SELL: {sell_n / total_directional:.0%} | "
            f"(FLAT مسجلة: {flat_n})"
        )

st.divider()

# ---------- الشارط التفاعلي ----------

fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="BTCUSDT",
    )
)

if not history.empty:
    buys = history[history["signal"] == "BUY"]
    sells = history[history["signal"] == "SELL"]

    if not buys.empty:
        fig.add_trace(
            go.Scatter(
                x=buys["date"],
                y=buys["price"] * 0.98,
                mode="markers",
                marker=dict(symbol="triangle-up", color="green", size=14),
                name="BUY",
                text=[f"BUY @ {p:,.0f}" for p in buys["price"]],
                hoverinfo="text",
            )
        )

    if not sells.empty:
        fig.add_trace(
            go.Scatter(
                x=sells["date"],
                y=sells["price"] * 1.02,
                mode="markers",
                marker=dict(symbol="triangle-down", color="red", size=14),
                name="SELL",
                text=[f"SELL @ {p:,.0f}" for p in sells["price"]],
                hoverinfo="text",
            )
        )

fig.update_layout(
    title="BTCUSDT - شموع يومية مع إشارات LS_ratio Contrarian",
    xaxis_title="التاريخ",
    yaxis_title="السعر (USDT)",
    xaxis_rangeslider_visible=True,
    height=650,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

with st.expander("📜 سجل الإشارات الكامل"):
    st.dataframe(history.sort_values("date", ascending=False), use_container_width=True)

with st.expander("ℹ️ معلومات الاستراتيجية"):
    st.markdown(
        f"""
        - **Z_THRESHOLD**: {Z_THRESHOLD} (فوقو SELL، تحت سالبو BUY)
        - **LS_z**: z-score لنسبة اللونغ/شورت على نافذة 60 يوم
        - المنطق: contrarian — إذا كثرة المتداولين لونغ بشكل غير طبيعي (z > threshold) → SELL، والعكس صحيح.
        """
    )
