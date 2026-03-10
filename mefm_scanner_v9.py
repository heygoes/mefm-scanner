# ============================================================
# MEFM スキャナー v9
# 2026年マクロ対応版
# ① 自動GO/CAUTION/PASS判定
# ② LINE通知にマクロ判定を含める
# ③ 週次シグナルも同時スキャン
# ============================================================

import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ---- Colab/GitHub自動切替 ----
try:
    import google.colab
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

if IN_COLAB:
    import os
    LINE_TOKEN = os.environ.get("LINE_TOKEN", "")
else:
    import os
    LINE_TOKEN = os.environ.get("LINE_TOKEN", "")

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "yfinance", "-q"])
    import yfinance as yf

# ============================================================
# 2026年マクロ判断テーブル（年1回更新）
# ============================================================
MACRO_TABLE = {
    # GO：積極エントリー
    "7011.T":"GO","7012.T":"GO","7013.T":"GO","6301.T":"GO","6326.T":"GO",
    "8306.T":"GO","8316.T":"GO","8411.T":"GO","8766.T":"GO","8750.T":"GO",
    "8601.T":"GO","8604.T":"GO","8593.T":"GO",
    "8035.T":"GO","6857.T":"GO","6920.T":"GO","6146.T":"GO","7735.T":"GO",
    "6981.T":"GO","6762.T":"GO","7741.T":"GO","6965.T":"GO",
    "9503.T":"GO","9502.T":"GO","9531.T":"GO",
    "5401.T":"GO","5411.T":"GO","5713.T":"GO","5714.T":"GO","5803.T":"GO","5801.T":"GO",
    "8001.T":"GO","8002.T":"GO","8053.T":"GO","8058.T":"GO","8031.T":"GO",
    # CAUTION：確認後判断
    "9432.T":"CAUTION","9433.T":"CAUTION","9434.T":"CAUTION",
    "9983.T":"CAUTION","6098.T":"CAUTION","6367.T":"CAUTION",
    "6954.T":"CAUTION","6861.T":"CAUTION","6971.T":"CAUTION",
    "4502.T":"CAUTION","4503.T":"CAUTION","4568.T":"CAUTION",
    "2802.T":"CAUTION","2914.T":"CAUTION","4452.T":"CAUTION",
    # PASS：ロングスキップ
    "7203.T":"PASS","7267.T":"PASS","7201.T":"PASS","7202.T":"PASS",
    "9101.T":"PASS","9104.T":"PASS",
    "9984.T":"PASS","4385.T":"PASS","4478.T":"PASS",
}

SECTOR_NAME = {
    "7011.T":"重工防衛","7012.T":"重工防衛","7013.T":"重工防衛",
    "6301.T":"重工防衛","6326.T":"重工防衛",
    "8306.T":"銀行保険","8316.T":"銀行保険","8411.T":"銀行保険",
    "8766.T":"銀行保険","8750.T":"銀行保険","8601.T":"銀行保険",
    "8604.T":"銀行保険","8593.T":"銀行保険",
    "8035.T":"半導体","6857.T":"半導体","6920.T":"半導体",
    "6146.T":"半導体","7735.T":"半導体","6981.T":"半導体",
    "6762.T":"半導体","7741.T":"半導体","6965.T":"半導体",
    "9503.T":"電力ガス","9502.T":"電力ガス","9531.T":"電力ガス",
    "5401.T":"鉄鋼非鉄","5411.T":"鉄鋼非鉄","5713.T":"鉄鋼非鉄",
    "5714.T":"鉄鋼非鉄","5803.T":"鉄鋼非鉄","5801.T":"鉄鋼非鉄",
    "8001.T":"商社","8002.T":"商社","8053.T":"商社",
    "8058.T":"商社","8031.T":"商社",
    "7203.T":"自動車","7267.T":"自動車",
    "9101.T":"海運","9104.T":"海運",
}

# スキャン対象（全92銘柄）
TICKERS = list(dict.fromkeys([
    "7012.T","7011.T","6861.T","6857.T","6762.T","6758.T",
    "6701.T","6702.T","6954.T","6971.T","5803.T","5401.T",
    "4502.T","4503.T","4523.T","4063.T","4188.T","4452.T",
    "3382.T","2802.T","9984.T","9983.T","9432.T","9433.T",
    "8306.T","8316.T","8411.T","8035.T","7203.T","7267.T",
    "6367.T","6301.T","6326.T","4661.T","3659.T","3923.T",
    "4385.T","4478.T","6098.T","9101.T","9104.T","8001.T",
    "8002.T","8053.T","8058.T","8601.T","8604.T","8766.T","8750.T",
    "9502.T","9503.T","9531.T","9020.T","9021.T","9022.T",
    "5713.T","5714.T","4568.T","4519.T","4527.T",
    "6902.T","6920.T","6981.T","7751.T","7741.T",
    "7201.T","7202.T","7205.T","6503.T","6504.T","6506.T",
    "5411.T","3407.T","3401.T","1801.T","1802.T","1928.T",
    "8801.T","8802.T","4689.T","4755.T","4751.T",
    "2269.T","2502.T","2914.T","9301.T","9202.T",
    "4543.T","6869.T","4307.T","4324.T","9719.T",
    # 追加銘柄
    "7974.T","8031.T","9434.T","6501.T","6146.T","7735.T",
    "7013.T","5801.T","6965.T","8593.T",
]))

def is_weekday():
    return datetime.now().weekday() < 5

def calc_atr(df, p=14):
    h,l,c=df["High"],df["Low"],df["Close"]
    tr=pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    return tr.rolling(p).mean()

def calc_bbw(df, p=20):
    c=df["Close"]
    return (c.rolling(p).std()*2)/(c.rolling(p).mean()+1e-9)

def calc_adx(df, p=14):
    h,l,c=df["High"],df["Low"],df["Close"]
    hd=h.diff(1);ld=l.shift(1)-l
    pdm=pd.Series(np.where((hd>ld)&(hd>0),hd,0.0),index=df.index)
    mdm=pd.Series(np.where((ld>hd)&(ld>0),ld,0.0),index=df.index)
    atr=calc_atr(df,p)
    pdi=100*pdm.rolling(p).mean()/(atr+1e-9)
    mdi=100*mdm.rolling(p).mean()/(atr+1e-9)
    dx=100*(pdi-mdi).abs()/(pdi+mdi+1e-9)
    return dx.rolling(p).mean()

def calc_rsi(df, p=14):
    d=df["Close"].diff(1)
    u=d.clip(lower=0);dn=-d.clip(upper=0)
    rs=u.rolling(p).mean()/(dn.rolling(p).mean()+1e-9)
    return 100-(100/(1+rs))

def send_line(msg, token):
    if not token:
        print("[LINE通知スキップ（トークン未設定）]")
        return
    requests.post(
        "https://notify-api.line.me/api/notify",
        headers={"Authorization": f"Bearer {token}"},
        data={"message": msg}
    )

def scan_mefm_swing(raw, nk_c):
    """MEFMスイング（A4条件）スキャン"""
    signals = []
    for ticker in TICKERS:
        try:
            df = raw[ticker].dropna(how="all")
            if len(df) < 200: continue
        except: continue

        atr=calc_atr(df);bbw=calc_bbw(df)
        adx=calc_adx(df);rsi=calc_rsi(df)
        c=df["Close"];nk=nk_c.reindex(df.index,method="ffill")
        i=-1

        cur_c=float(c.iloc[i])
        ma5=float(c.iloc[i-5:i].mean())
        ma20=float(c.iloc[i-20:i].mean())
        ma60=float(c.iloc[i-60:i].mean())
        ma100=float(c.iloc[i-100:i].mean())
        atr_n=float(atr.iloc[i])
        atr_mx=float(atr.iloc[i-60:i].max())
        bbw_n=float(bbw.iloc[i])
        bbw_mx=float(bbw.iloc[i-60:i].max())
        mom60=(cur_c-float(c.iloc[i-60]))/(float(c.iloc[i-60])+1e-9)
        dev=(cur_c-ma20)/ma20
        rsi_n=float(rsi.iloc[i])
        adx_n=float(adx.iloc[i])
        nk_m20=float(nk.iloc[i-20:i].mean())
        nk_m60=float(nk.iloc[i-60:i].mean())

        if cur_c<=ma100: continue
        if not(ma5>ma20>ma60): continue
        if atr_mx<=0 or bbw_mx<=0: continue
        if (atr_n/atr_mx)>=0.65 or (bbw_n/bbw_mx)>=0.60: continue
        if mom60<0.05 or adx_n<20: continue
        if not(-0.06<=dev<=-0.003): continue
        if rsi_n<=55: continue
        if nk_m20<=nk_m60: continue

        macro = MACRO_TABLE.get(ticker, "UNKNOWN")
        sector= SECTOR_NAME.get(ticker, "その他")
        sl    = cur_c - atr_n*1.5
        tp    = cur_c * 1.07

        signals.append({
            "ticker": ticker,
            "macro":  macro,
            "sector": sector,
            "price":  round(cur_c, 0),
            "tp":     round(tp, 0),
            "sl":     round(sl, 0),
            "rsi":    round(rsi_n, 1),
            "dev":    round(dev*100, 1),
        })
    return signals

def scan_weekly(raw, nk_c):
    """週次スキャン（緩め条件・3〜5日保有）"""
    signals = []
    for ticker in TICKERS:
        try:
            df = raw[ticker].dropna(how="all")
            if len(df) < 130: continue
        except: continue

        bbw=calc_bbw(df);rsi=calc_rsi(df)
        c=df["Close"];nk=nk_c.reindex(df.index,method="ffill")
        i=-1

        cur_c=float(c.iloc[i])
        ma5=float(c.iloc[i-5:i].mean())
        ma20=float(c.iloc[i-20:i].mean())
        ma60=float(c.iloc[i-60:i].mean())
        bbw_n=float(bbw.iloc[i])
        bbw_avg=float(bbw.iloc[i-40:i].mean())
        dev=(cur_c-ma20)/ma20
        rsi_n=float(rsi.iloc[i])
        nk_m20=float(nk.iloc[i-20:i].mean())
        nk_m60=float(nk.iloc[i-60:i].mean())

        if cur_c<=ma60: continue
        if not(ma5>ma20): continue
        if bbw_avg<=0: continue
        if bbw_n>=bbw_avg*0.70: continue
        if not(-0.05<=dev<=-0.001): continue
        if rsi_n<=50: continue
        if nk_m20<=nk_m60: continue

        macro = MACRO_TABLE.get(ticker, "UNKNOWN")
        if macro == "PASS": continue  # PASSはスキップ

        signals.append({
            "ticker": ticker,
            "macro":  macro,
            "price":  round(cur_c, 0),
            "tp":     round(cur_c*1.04, 0),
            "sl":     round(cur_c*0.975, 0),
            "rsi":    round(rsi_n, 1),
        })
    return signals

# ============================================================
# メイン実行
# ============================================================
def main():
    today = datetime.now()
    print(f"MEFM v9 スキャナー 実行: {today.strftime('%Y-%m-%d %H:%M')}")

    if not is_weekday():
        msg = f"\nMEFM v9\n{today.strftime('%m/%d')} 本日は土日のためスキャンをスキップします"
        print(msg)
        send_line(msg, LINE_TOKEN)
        return

    print("データ取得中...")
    raw = yf.download(TICKERS, period="1y", interval="1d",
                      group_by="ticker", auto_adjust=True,
                      progress=False, threads=True)
    nk_raw = yf.download("^N225", period="1y", interval="1d",
                         progress=False, auto_adjust=True)
    if isinstance(nk_raw.columns, pd.MultiIndex):
        nk_raw.columns = [col[0] for col in nk_raw.columns]
    nk_c = nk_raw["Close"]
    print("完了")

    # スキャン実行
    swing_sigs = scan_mefm_swing(raw, nk_c)
    weekly_sigs = scan_weekly(raw, nk_c)

    # ---- GO/CAUTION別に分類 ----
    swing_go      = [s for s in swing_sigs if s["macro"]=="GO"]
    swing_caution = [s for s in swing_sigs if s["macro"]=="CAUTION"]
    swing_pass    = [s for s in swing_sigs if s["macro"]=="PASS"]
    weekly_go     = [s for s in weekly_sigs if s["macro"]=="GO"]

    # ---- コンソール出力 ----
    print(f"\n{'='*55}")
    print(f"  MEFMスイング シグナル: {len(swing_sigs)}件")
    print(f"    GO      : {len(swing_go)}件")
    print(f"    CAUTION : {len(swing_caution)}件")
    print(f"    PASS    : {len(swing_pass)}件")
    print(f"  週次シグナル    : {len(weekly_go)}件（GO銘柄のみ）")
    print(f"{'='*55}")

    if swing_go:
        print(f"\n[スイング GO銘柄]")
        for s in swing_go:
            print(f"  {s['ticker']} ({s['sector']}) "
                  f"現値:{s['price']} TP:{s['tp']} SL:{s['sl']} "
                  f"RSI:{s['rsi']} 乖離:{s['dev']}%")

    if swing_caution:
        print(f"\n[スイング CAUTION銘柄]（要確認）")
        for s in swing_caution:
            print(f"  {s['ticker']} 現値:{s['price']} RSI:{s['rsi']}")

    if weekly_go:
        print(f"\n[週次 GO銘柄]（3〜5日保有）")
        for s in weekly_go:
            print(f"  {s['ticker']} 現値:{s['price']} TP:{s['tp']} SL:{s['sl']}")

    # ---- LINE通知 ----
    date_str = today.strftime("%m/%d(%a)")
    msg_parts = [f"\nMEFM v9 [{date_str}]"]

    if swing_go:
        msg_parts.append(f"\n[スイング GO] {len(swing_go)}件")
        for s in swing_go:
            msg_parts.append(
                f"  {s['ticker']}({s['sector']})\n"
                f"  現値:{s['price']} TP:{s['tp']} SL:{s['sl']}\n"
                f"  RSI:{s['rsi']} 乖離:{s['dev']}%"
            )
    elif swing_caution:
        msg_parts.append(f"\n[CAUTION] {len(swing_caution)}件（要確認）")
        for s in swing_caution[:2]:
            msg_parts.append(f"  {s['ticker']} 現値:{s['price']}")
    else:
        msg_parts.append("\n[スイング] シグナルなし")

    if weekly_go:
        msg_parts.append(f"\n[週次 GO] {len(weekly_go)}件")
        for s in weekly_go[:3]:
            msg_parts.append(f"  {s['ticker']} 現値:{s['price']} TP:{s['tp']}")

    if not swing_sigs and not weekly_go:
        msg_parts.append("\n本日シグナルなし")

    msg_parts.append(f"\n2026年優先: 重工防衛/銀行/半導体/電力/鉄鋼/商社")

    send_line("\n".join(msg_parts), LINE_TOKEN)
    print("\nLINE通知送信完了")

main()
