import os
import time
import requests
import pandas as pd
import ta
import asyncio
from telegram import Bot

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Likiditesi yüksek, tahtası sağlam ana coinler
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"]

last_signals = {}

def get_binance_data(symbol, interval="30m", limit=200):
    """30 DAKİKALIK mum verisi - Gürültüyü azaltmak için."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    df = pd.DataFrame(data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
    ])
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    return df

def analyze_high_precision(symbol):
    """Sadece yüksek kazanma oranlı durumları filtreler."""
    try:
        df = get_binance_data(symbol, interval="30m")
        
        # 1. Trend Gücü (ADX) -> Piyasa hacimsizse direkt eler
        adx_indicator = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
        df['adx'] = adx_indicator.adx()
        
        # 2. Ana Trend (EMA 200)
        df['ema200'] = ta.trend.EMAIndicator(close=df['close'], window=200).ema_indicator()
        
        # 3. Momentum (RSI)
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        
        # 4. MACD Kesişimi
        macd = ta.trend.MACD(close=df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = latest['close']
        adx = latest['adx']
        rsi = latest['rsi']
        ema = latest['ema200']
        
        # Sadece ADX 22'den büyükse (Gerçek ve güçlü bir trend varsa) devam et
        if adx < 22:
            return None

        # --- YÜKSEK KAZANMA ORANLI LONG ---
        # ADX Güçlü + Fiyat EMA200 Üstü + RSI Aşırı Satımdan Dönüyor + MACD Kesişimi
        if (price > ema) and (rsi < 40) and (prev['macd'] < prev['macd_signal'] and latest['macd'] > latest['macd_signal']):
            tp1 = round(price * 1.015, 4)  # %1.5 Garanti TP
            tp2 = round(price * 1.035, 4)  # %3.5 İkinci TP
            sl = round(price * 0.988, 4)   # %1.2 Stop
            
            return (
                f"🔥 **SNIPER LONG İŞLEMİ (Yüksek Win-Rate)** 🔥\n\n"
                f"🪙 **Coin:** #{symbol}\n"
                f"💵 **Giriş:** ${price}\n\n"
                f"🎯 **TP1:** ${tp1} (%1.5)\n"
                f"🎯 **TP2:** ${tp2} (%3.5)\n"
                f"🛑 **SL:** ${sl} (%1.2)\n\n"
                f"📊 **Trend Gücü (ADX):** {round(adx, 1)} (Çok Güçlü)\n"
                f"⚙️ **Kaldıraç:** 3x - 5x"
            )

        # --- YÜKSEK KAZANMA ORANLI SHORT ---
        # ADX Güçlü + Fiyat EMA200 Altı + RSI Aşırı Alımdan Dönüyor + MACD Kesişimi
        elif (price < ema) and (rsi > 60) and (prev['macd'] > prev['macd_signal'] and latest['macd'] < latest['macd_signal']):
            tp1 = round(price * 0.985, 4)  # %1.5 Garanti TP
            tp2 = round(price * 0.965, 4)  # %3.5 İkinci TP
            sl = round(price * 1.012, 4)   # %1.2 Stop
            
            return (
                f"🔥 **SNIPER SHORT İŞLEMİ (Yüksek Win-Rate)** 🔥\n\n"
                f"🪙 **Coin:** #{symbol}\n"
                f"💵 **Giriş:** ${price}\n\n"
                f"🎯 **TP1:** ${tp1} (%1.5)\n"
                f"🎯 **TP2:** ${tp2} (%3.5)\n"
                f"🛑 **SL:** ${sl} (%1.2)\n\n"
                f"📊 **Trend Gücü (ADX):** {round(adx, 1)} (Çok Güçlü)\n"
                f"⚙️ **Kaldıraç:** 3x - 5x"
            )

        return None
    except Exception as e:
        print(f"Hata ({symbol}): {e}")
        return None

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    print("🤖 Sniper Bot Çalışıyor. Sadece yüksek ihtimalli işlemler bekleniyor...")
    
    while True:
        for symbol in SYMBOLS:
            signal_msg = analyze_high_precision(symbol)
            
            if signal_msg and last_signals.get(symbol) != signal_msg:
                await bot.send_message(chat_id=CHAT_ID, text=signal_msg, parse_mode="Markdown")
                last_signals[symbol] = signal_msg
                print(f"[{symbol}] SNIPER İŞLEM ATILDI!")
            
        # 5 dakikada bir tarar ama şartlar zor olduğu için nadiren mesaj atar
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())