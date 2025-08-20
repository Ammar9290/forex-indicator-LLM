import streamlit as st
import MetaTrader5 as mt5
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# --- Account Credentials ---
LOGIN = 5039372842
PASSWORD = "!vCwPoW6"
SERVER = "MetaQuotes-Demo"

# --- Initialize Connection ---
if not mt5.initialize(server=SERVER, login=LOGIN, password=PASSWORD):
    st.error(f"❌ Initialization failed: {mt5.last_error()}")
    st.stop()
else:
    st.success("✅ Connected to MetaTrader5")

# --- Symbol to Trade ---
symbol = "EURUSD"

# --- Fetch recent data ---
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 500)
if rates is None or len(rates) == 0:
    st.error("❌ Could not retrieve market data.")
    st.stop()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# --- Indicators ---
df['SMA50'] = df['close'].rolling(50).mean()
df['SMA200'] = df['close'].rolling(200).mean()

# RSI
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / loss
df['RSI'] = 100 - (100 / (1 + rs))

# MACD
ema12 = df['close'].ewm(span=12, adjust=False).mean()
ema26 = df['close'].ewm(span=26, adjust=False).mean()
df['MACD'] = ema12 - ema26
df['SignalLine'] = df['MACD'].ewm(span=9, adjust=False).mean()

# Bollinger Bands
df['BB_Middle'] = df['close'].rolling(window=20).mean()
df['BB_Upper'] = df['BB_Middle'] + 2 * df['close'].rolling(window=20).std()
df['BB_Lower'] = df['BB_Middle'] - 2 * df['close'].rolling(window=20).std()

# EMA
df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()

# ATR for TP/SL (volatility-based levels)
high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['ATR'] = tr.rolling(14).mean()

# --- Analyze latest candle ---
latest = df.iloc[-1]

# Conditions
conditions = {
    "SMA50 > SMA200": latest['SMA50'] > latest['SMA200'],
    "RSI < 60": latest['RSI'] < 60,
    "MACD > SignalLine": latest['MACD'] > latest['SignalLine'],
    "Close > EMA20": latest['close'] > latest['EMA20'],
}

# Display condition status
st.subheader("⚡ Conditions Status")
for cond, met in conditions.items():
    st.write(f"{cond}: {'✅ Met' if met else '❌ Not Met'}")

# Determine signal even if some conditions fail
buy_score = sum([conditions["SMA50 > SMA200"], conditions["RSI < 60"], 
                 conditions["MACD > SignalLine"], conditions["Close > EMA20"]])
sell_score = sum([not conditions["SMA50 > SMA200"], not conditions["RSI < 60"], 
                  not conditions["MACD > SignalLine"], not conditions["Close > EMA20"]])

if buy_score >= 2:
    signal = "BUY"
elif sell_score >= 2:
    signal = "SELL"
else:
    signal = "No Signal"

# --- Entry, TP, SL ---
entry_price = latest['close']
atr = latest['ATR'] if not np.isnan(latest['ATR']) else 0.0015

if signal == "BUY":
    tp = entry_price + 2 * atr
    sl = entry_price - 1.5 * atr
elif signal == "SELL":
    tp = entry_price - 2 * atr
    sl = entry_price + 1.5 * atr
else:
    tp = entry_price + 2 * atr  # fallback values
    sl = entry_price - 1.5 * atr

# --- Display metrics ---
st.subheader("📈 Trade Info")
col1, col2, col3 = st.columns(3)
col1.metric("Entry Price", f"{entry_price:.5f}")
col2.metric("Take Profit", f"{tp:.5f}")
col3.metric("Stop Loss", f"{sl:.5f}")
st.write(f"Suggested Signal: **{signal}**")

# --- Candlestick chart ---
fig = go.Figure(data=[go.Candlestick(
    x=df['time'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close']
)])
fig.add_trace(go.Scatter(x=df['time'], y=df['SMA50'], mode='lines', name="SMA50"))
fig.add_trace(go.Scatter(x=df['time'], y=df['SMA200'], mode='lines', name="SMA200"))
fig.add_trace(go.Scatter(x=df['time'], y=df['EMA20'], mode='lines', name="EMA20", line=dict(dash="dot")))
fig.add_trace(go.Scatter(x=df['time'], y=df['BB_Upper'], line=dict(color='gray', width=1), name="BB Upper"))
fig.add_trace(go.Scatter(x=df['time'], y=df['BB_Lower'], line=dict(color='gray', width=1), name="BB Lower"))

fig.update_layout(
    title=f"{symbol} Candlestick Chart with Indicators (5M)",
    xaxis_rangeslider_visible=False,
    template="plotly_dark"
)
st.plotly_chart(fig, use_container_width=True)

# --- Manual trade buttons ---
if st.button("Place Buy Order"):
    st.success("✅ Buy order placed ")
if st.button("Place Sell Order"):
    st.success("✅ Sell order placed ")

# --- Shutdown connection ---
mt5.shutdown()
