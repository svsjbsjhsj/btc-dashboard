"""
data_fetch.py
جلب بيانات BTC (الشموع اليومية + Long/Short Ratio) من Binance Futures API.
 
ملاحظة مهمة:
- fapi.binance.com قد يعطي خطأ 451 (Geo-block) في بعض بيئات الاستضافة
  (مثل Google Colab أو بعض السيرفرات السحابية).
- إذا صار هذا، أول حل هو تشغيل التطبيق من بيئة/شبكة مختلفة (محلي، VPS، إلخ)
  أو تفعيل VPN/Proxy على مستوى الشبكة.
- هذا الملف يحاول أولاً بطلب مباشر، وإذا فشل يعيد المحاولة برأس User-Agent
  يحاكي متصفح حقيقي، وإن فشل الاثنان يرجع خطأ واضح للواجهة بدل الانهيار.
"""
 
import requests
import pandas as pd
import streamlit as st
 
BASE_URL = "https://fapi.binance.com"
 
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
 
 
class DataFetchError(Exception):
    """يُرفع عندما يفشل جلب البيانات من Binance بكل الطرق المتاحة."""
    pass
 
 
def _get_with_fallback(url: str, params: dict) -> list:
    """
    يحاول GET مباشر بلا headers خاصة، وإذا فشل (451 أو أي خطأ شبكة)
    يعاود المحاولة بـ headers متصفح حقيقي، وإذا فشل يعاود عبر proxy عام
    (مفيد لما التطبيق يكون مستضاف على سيرفر أمريكي محظور من Binance، بحال
    Streamlit Community Cloud).
    """
    last_error = None
    full_url_with_params = requests.Request("GET", url, params=params).prepare().url
 
    # المحاولة 1: طلب مباشر بسيط
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except requests.RequestException as e:
        last_error = str(e)
 
    # المحاولة 2: headers متصفح حقيقي
    try:
        resp = requests.get(url, params=params, headers=BROWSER_HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except requests.RequestException as e:
        last_error = str(e)
 
    # المحاولة 3+: عبر عدة proxies عامة (fallback chain) - يفيد إذا كان
    # سيرفر الاستضافة نفسه محظور جغرافياً (مثل GCP us-central1 اللي
    # كيستعملها Streamlit Cloud)، أو إذا كان proxy واحد معطل مؤقتاً
    proxy_builders = [
        lambda u: "https://api.codetabs.com/v1/proxy?quest=" + requests.utils.quote(u, safe=""),
        lambda u: "https://api.allorigins.win/raw?url=" + requests.utils.quote(u, safe=""),
    ]
    for build_proxy_url in proxy_builders:
        try:
            proxy_url = build_proxy_url(full_url_with_params)
            resp = requests.get(proxy_url, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            last_error = f"(proxy) HTTP {resp.status_code}: {resp.text[:200]}"
        except (requests.RequestException, ValueError) as e:
            last_error = f"(proxy) {e}"
 
    raise DataFetchError(
        f"فشل جلب البيانات من {url}\n"
        f"آخر خطأ: {last_error}\n"
        f"إذا كان الخطأ 451 (Geo-block)، جرب تشغيل التطبيق من بيئة/شبكة مختلفة "
        f"(سيرفر محلي، VPS، أو مع VPN)."
    )
 
 
@st.cache_data(ttl=300, show_spinner=False)
def fetch_klines(symbol: str = "BTCUSDT", interval: str = "1d", limit: int = 500) -> pd.DataFrame:
    """
    يجيب بيانات الشموع (OHLCV) من Binance Futures.
    يرجع DataFrame بأعمدة: date, open, high, low, close, volume
    """
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    raw = _get_with_fallback(url, params)
 
    cols = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(raw, columns=cols)
 
    df["date"] = pd.to_datetime(df["open_time"], unit="ms").dt.date
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
 
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("date").reset_index(drop=True)
    return df
 
 
@st.cache_data(ttl=300, show_spinner=False)
def fetch_long_short_ratio(symbol: str = "BTCUSDT", period: str = "1d", limit: int = 500) -> pd.DataFrame:
    """
    يجيب نسبة اللونغ/شورت العالمية (Global Long/Short Account Ratio).
    يرجع DataFrame بأعمدة: date, longShortRatio
    """
    url = f"{BASE_URL}/futures/data/globalLongShortAccountRatio"
    params = {"symbol": symbol, "period": period, "limit": limit}
    raw = _get_with_fallback(url, params)
 
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.date
    df["longShortRatio"] = df["longShortRatio"].astype(float)
 
    df = df[["date", "longShortRatio"]]
    df = df.sort_values("date").reset_index(drop=True)
    return df
 
 
def fetch_merged_data(symbol: str = "BTCUSDT", limit: int = 500) -> pd.DataFrame:
    """
    يجيب الشموع + نسبة اللونغ/شورت ويدمجهم فـ DataFrame واحد على أساس التاريخ.
    """
    klines = fetch_klines(symbol=symbol, limit=limit)
    ls_ratio = fetch_long_short_ratio(symbol=symbol, limit=limit)
 
    merged = pd.merge(klines, ls_ratio, on="date", how="inner")
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged
