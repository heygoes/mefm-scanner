# ============================================================
# MEFM-Pro Scanner v6c Fast + LINE通知 完全版
# ============================================================

import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# LINE設定
# ============================================================

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
USER_ID = os.getenv("LINE_USER_ID")

def send_line(message):

    if not LINE_TOKEN or not USER_ID:
        print("LINEトークン未設定")
        return

    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}"
    }

    data = {
        "to": USER_ID,
        "messages":[
            {
                "type":"text",
                "text": message[:5000]
            }
        ]
    }

    try:
        requests.post(url, headers=headers, json=data, timeout=10)
    except Exception as e:
        print("LINE送信失敗:", e)

# ============================================================
# 日付設定
# ============================================================

END      = datetime.today().strftime("%Y-%m-%d")
START    = (datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d")
NK_START = (datetime.today() - timedelta(days=500)).strftime("%Y-%m-%d")

# ============================================================
# 監視銘柄
# ============================================================

TICKERS = [
"7012.T","7011.T","6861.T","6857.T","6762.T","6758.T",
"6701.T","6702.T","6954.T","6971.T","5803.T","5401.T",
"4502.T","4503.T","4523.T","4063.T","4188.T","4452.T",
"3382.T","2802.T","9984.T","9983.T","9432.T","9433.T",
"8306.T","8316.T","8411.T","8035.T","7203.T","7267.T",
"6367.T","6301.T","6326.T","4661.T","3659.T","3923.T",
"4385.T","4478.T","6098.T","9101.T","9104.T","8001.T",
"6594.T","6645.T","6723.T","6770.T","6841.T",
"6902.T","6920.T","6963.T","6981.T","7735.T",
"7741.T","7751.T","7752.T","4543.T","6586.T",
"6471.T","6472.T","6473.T","6503.T","6504.T",
"6506.T","6674.T","6753.T","6806.T",
"6869.T","6952.T","7004.T","7013.T",
"7201.T","7202.T","7205.T","7211.T","7261.T",
"7269.T","7270.T","7272.T","7309.T","7762.T"
]

TICKERS = list(dict.fromkeys(TICKERS))

# ============================================================
# データ一括取得
# ============================================================

def download_all(tickers,start,end,batch_size=50):

    all_data={}
    batches=[tickers[i:i+batch_size] for i in range(0,len(tickers),batch_size)]

    for batch in batches:

        raw=yf.download(
            tickers=batch,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True
        )

        if len(batch)==1:

            if not raw.empty:
                all_data[batch[0]]=raw

        else:

            for ticker in batch:

                try:
                    df=raw.xs(ticker,axis=1,level=1).dropna(how="all")
                    if len(df)>=100:
                        all_data[ticker]=df
                except:
                    pass

    return all_data

# ============================================================
# 指標
# ============================================================

def calc_atr(df,period=14):

    h,l,c=df["High"],df["Low"],df["Close"]

    tr=pd.concat([
        h-l,
        (h-c.shift(1)).abs(),
        (l-c.shift(1)).abs()
    ],axis=1).max(axis=1)

    return tr.rolling(period).mean()

def calc_rsi(df,period=14):

    delta=df["Close"].diff()

    up=delta.clip(lower=0)
    down=-delta.clip(upper=0)

    rs=up.rolling(period).mean()/(down.rolling(period).mean()+1e-9)

    return 100-(100/(1+rs))

# ============================================================
# シグナル判定
# ============================================================

def check_signal(ticker,df):

    try:

        if len(df)<120:
            return None

        c=df["Close"]

        ma5=c.rolling(5).mean()
        ma20=c.rolling(20).mean()
        ma60=c.rolling(60).mean()

        i=len(df)-1

        if not(ma5[i]>ma20[i]>ma60[i]):
            return None

        if c[i]<=df["High"][i-1]:
            return None

        rsi=calc_rsi(df)

        if rsi[i]<50:
            return None

        atr=calc_atr(df)

        close=float(c[i])

        tp=int(close*1.07)
        sl=int(close-atr[i]*1.5)

        sl_pct=round((close-sl)/close*100,2)

        return {
            "ticker":ticker,
            "close":int(close),
            "prev_high":int(df["High"][i]),
            "tp_price":tp,
            "sl_price":sl,
            "sl_pct":sl_pct
        }

    except:
        return None

# ============================================================
# メイン処理
# ============================================================

today_str=datetime.today().strftime("%Y年%m月%d日")

print("MEFM Scanner 起動",today_str)

# 日経取得
nk=yf.download("^N225",start=NK_START,end=END,progress=False)

nk_close=nk["Close"]

nk_ma20=nk_close.rolling(20).mean().iloc[-1]
nk_ma60=nk_close.rolling(60).mean().iloc[-1]

nk_ok=nk_ma20>nk_ma60

signals=[]

if nk_ok:

    data=download_all(TICKERS,START,END)

    for ticker,df in data.items():

        result=check_signal(ticker,df)

        if result:
            signals.append(result)

# ============================================================
# LINE送信
# ============================================================

if not nk_ok:

    send_line(
        f"⚠️ MEFM {today_str}\n"
        "日経トレンド条件未達\n"
        "本日はエントリー見送り"
    )

else:

    if not signals:

        send_line(
            f"📭 MEFMシグナル {today_str}\n"
            "該当銘柄なし"
        )

    else:

        text=f"📈 MEFMシグナル {today_str}\n"
        text+=f"検出銘柄数: {len(signals)}\n\n"

        for s in signals:

            tp_pct=round((s["tp_price"]-s["close"])/s["close"]*100,1)

            text+=(
              f"📌 {s.get('ticker','?')}\n"
                f"終値 {close:,}円\n"
                f"買いライン {prev_high:,}円\n"
                f"利確 +{tp_pct}% → {tp_price:,}円\n"
                f"損切 -{sl_pct}% → {sl_price:,}円\n"
                f"保有 {hold_days}日\n\n"
            )

        send_line(text)

print("スキャン終了")
