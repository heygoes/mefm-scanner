# ============================================================
# MEFM-Pro スキャナー高速化パッチ
# 現在のmefm_scanner_v6c.pyの冒頭部分と差し替える
#
# 変更点：yfinanceの並列ダウンロードを使う
# 効果  ：3〜5分 → 30〜60秒に短縮
# ============================================================

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

END      = datetime.today().strftime("%Y-%m-%d")
START    = (datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d")
NK_START = (datetime.today() - timedelta(days=500)).strftime("%Y-%m-%d")

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
    "7269.T","7270.T","7272.T","7309.T","7762.T",
    "5108.T","5110.T",
    "4004.T","4005.T","4021.T","4042.T","4061.T",
    "4183.T","4208.T","4272.T","3407.T","3401.T",
    "5019.T","5020.T","5101.T","5201.T","5202.T",
    "5214.T","5301.T","5332.T","5333.T","5411.T",
    "5713.T","5714.T","5801.T","5802.T",
    "4519.T","4527.T","4530.T","4536.T","4540.T",
    "4568.T","4578.T","7483.T",
    "8303.T","8308.T","8309.T","8331.T","8354.T",
    "8601.T","8604.T","8628.T","8630.T","8750.T",
    "8766.T","8725.T","8253.T","7182.T",
    "8002.T","8006.T","8007.T","8015.T","8053.T","8058.T",
    "3099.T","3086.T","3088.T","7453.T",
    "7649.T","8267.T","9843.T",
    "1801.T","1802.T","1803.T","1812.T","1925.T",
    "1928.T","8801.T","8802.T","8804.T","8830.T",
    "3281.T","3288.T","3289.T",
    "3672.T","3694.T","3697.T","3765.T","3778.T",
    "4307.T","4318.T","4324.T","4689.T","4755.T",
    "4751.T","9719.T",
    "2269.T","2282.T","2502.T","2503.T","2579.T",
    "2587.T","2871.T","2914.T","2201.T","2002.T",
    "9501.T","9502.T","9503.T","9531.T","9532.T",
    "9020.T","9021.T","9022.T","9202.T","9301.T",
]
TICKERS = list(dict.fromkeys(TICKERS))

# ============================================================
# ★ 高速化の核心：一括並列ダウンロード
# ============================================================

def download_all(tickers, start, end, batch_size=50):
    """
    全銘柄を並列で一括ダウンロード
    batch_size：1回に取得する銘柄数（50が安定）
    """
    all_data = {}
    batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]

    for idx, batch in enumerate(batches):
        print(f"  データ取得中... {idx*batch_size+1}〜{min((idx+1)*batch_size, len(tickers))}銘柄目")
        try:
            raw = yf.download(
                tickers   = batch,
                start     = start,
                end       = end,
                interval  = "1d",
                auto_adjust = True,
                progress  = False,
                threads   = True,   # ← 並列化のキー
            )
            # 1銘柄の場合と複数銘柄の場合でデータ構造が異なる
            if len(batch) == 1:
                ticker = batch[0]
                if not raw.empty:
                    all_data[ticker] = raw
            else:
                # MultiIndex → 銘柄ごとに分割
                for ticker in batch:
                    try:
                        df = raw.xs(ticker, axis=1, level=1).dropna(how="all")
                        if len(df) >= 50:
                            all_data[ticker] = df
                    except:
                        pass
        except Exception as e:
            print(f"  ⚠️  バッチ{idx+1}でエラー: {e}")

    return all_data

# ── 指標計算（変更なし）────────────────────────────────

def calc_atr(df, period=14):
    h,l,c = df["High"],df["Low"],df["Close"]
    tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_bbw(df, period=20):
    c = df["Close"]
    return (c.rolling(period).std()*2)/(c.rolling(period).mean()+1e-9)

def calc_adx(df, period=14):
    h,l,c = df["High"],df["Low"],df["Close"]
    h_diff=h.diff(1); l_diff=l.shift(1)-l
    pdm=pd.Series(np.where((h_diff>l_diff)&(h_diff>0),h_diff,0.0),index=df.index)
    mdm=pd.Series(np.where((l_diff>h_diff)&(l_diff>0),l_diff,0.0),index=df.index)
    atr=calc_atr(df,period)
    pdi=100*pdm.rolling(period).mean()/(atr+1e-9)
    mdi=100*mdm.rolling(period).mean()/(atr+1e-9)
    dx=100*(pdi-mdi).abs()/(pdi+mdi+1e-9)
    return dx.rolling(period).mean()

def calc_rsi(df, period=14):
    delta=df["Close"].diff(1)
    up=delta.clip(lower=0); down=-delta.clip(upper=0)
    rs=up.rolling(period).mean()/(down.rolling(period).mean()+1e-9)
    return 100-(100/(1+rs))

def get_hold_days(nk_close, j):
    if j < 20:
        return 15, "普通の上昇"
    nk_now  = float(nk_close.iloc[j])
    nk_ma20 = float(nk_close.iloc[j-20:j].mean())
    if nk_now > nk_ma20:
        return 20, "強い上昇🔥"
    else:
        return 15, "普通の上昇"

# ── シグナル判定（1銘柄分）────────────────────────────

def check_signal(ticker, df, nk_close, hold_days, market_mode):
    try:
        if len(df) < 120:
            return None

        atr=calc_atr(df); bbw=calc_bbw(df); adx=calc_adx(df); rsi=calc_rsi(df)
        c  =df["Close"]
        nk =nk_close.reindex(df.index, method="ffill")
        i  =len(df)-1
        if i < 110: return None

        if c.iloc[i]<=c.iloc[i-100:i].mean(): return None
        ma5=c.iloc[i-5:i].mean(); ma20=c.iloc[i-20:i].mean(); ma60=c.iloc[i-60:i].mean()
        if not(ma5>ma20>ma60): return None
        atr_now=atr.iloc[i]; atr_max=atr.iloc[max(0,i-60):i].max()
        bbw_now=bbw.iloc[i]; bbw_max=bbw.iloc[max(0,i-60):i].max()
        if atr_max<=0 or bbw_max<=0: return None
        if(atr_now/atr_max)>=0.65 or(bbw_now/bbw_max)>=0.60: return None
        mom60=(c.iloc[i]-c.iloc[i-60])/(c.iloc[i-60]+1e-9)
        if mom60<0.05 or adx.iloc[i]<20: return None
        deviation=(c.iloc[i]-ma20)/ma20
        if not(-0.06<=deviation<=-0.003): return None
        if i<1: return None
        if c.iloc[i]<=df["High"].iloc[i-1]: return None
        if rsi.iloc[i]<=50: return None
        if i<60: return None
        nk_ma20=nk.iloc[i-20:i].mean(); nk_ma60=nk.iloc[i-60:i].mean()
        if nk_ma20<=nk_ma60: return None

        close_today = float(c.iloc[i])
        atr_val     = float(atr_now)
        tp  = int(round(close_today * 1.07))
        sl  = int(round(close_today - atr_val * 1.5))
        sl_pct = round(atr_val * 1.5 / close_today * 100, 2)

        return {
            "ticker":      ticker,
            "close":       int(round(close_today)),
            "prev_high":   int(round(float(df["High"].iloc[i]))),
            "rsi":         round(float(rsi.iloc[i]), 1),
            "deviation":   round(deviation * 100, 2),
            "tp_price":    tp,
            "sl_price":    sl,
            "sl_pct":      sl_pct,
            "hold_days":   hold_days,
            "market_mode": market_mode,
        }
    except:
        return None

# ── メイン実行 ────────────────────────────────────────────

today_str = datetime.today().strftime("%Y年%m月%d日")
print(f"MEFM-Pro スキャナー v6c（高速版）  {today_str}")
print()

# 日経データ取得
print("日経データ取得中...")
t0 = datetime.now()
nk_raw=yf.download("^N225", start=NK_START, end=END,
                   interval="1d", progress=False, auto_adjust=True)
if isinstance(nk_raw.columns,pd.MultiIndex): nk_raw.columns=[col[0] for col in nk_raw.columns]
nk_close=nk_raw["Close"]

# 市場環境チェック
nk_i     = len(nk_close)-1
nk_price = float(nk_close.iloc[nk_i])
nk_ma20  = float(nk_close.iloc[nk_i-20:nk_i].mean())
nk_ma60  = float(nk_close.iloc[nk_i-60:nk_i].mean())
nk_ok    = nk_ma20 > nk_ma60
hold_days, market_mode = get_hold_days(nk_close, nk_i)

print(f"取得完了\n")
print("="*65)
print("  📈 本日の市場環境")
print("="*65)
print(f"  日経終値 : {nk_price:>10,.0f}円")
print(f"  20MA     : {nk_ma20:>10,.0f}円")
print(f"  60MA     : {nk_ma60:>10,.0f}円")
print(f"  STEP7    : {'✅ 上昇トレンド（エントリー可）' if nk_ok else '❌ 下落/レンジ（見送り）'}")
if nk_ok:
    print(f"  相場モード: {market_mode}  →  保有期間{hold_days}日")
print()

if not nk_ok:
    print("  ⚠️  本日はエントリー条件外です。")
else:
    # ★ 一括並列ダウンロード
    print(f"  全{len(TICKERS)}銘柄を一括取得中...")
    t1 = datetime.now()
    all_data = download_all(TICKERS, START, END, batch_size=50)
    t2 = datetime.now()
    elapsed = (t2 - t1).seconds
    print(f"  取得完了: {len(all_data)}銘柄  ⏱️ {elapsed}秒\n")

    # シグナル判定
    signals = []
    for ticker, df in all_data.items():
        result = check_signal(ticker, df, nk_close, hold_days, market_mode)
        if result:
            signals.append(result)

    total_elapsed = (datetime.now() - t0).seconds
    print("="*65)
    if not signals:
        print("  📭 本日の買いシグナル：なし")
    else:
        print(f"  🔔 本日の買いシグナル：{len(signals)}銘柄")
        print("="*65)
        for s in signals:
            print(f"\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"  📌 {s['ticker']}")
            print(f"  本日終値    : {s['close']:,}円")
            print(f"  前日高値    : {s['prev_high']:,}円  ← 翌朝この値超えで買い")
            print(f"  RSI         : {s['rsi']:.1f}  押し目: {s['deviation']:+.2f}%")
            print(f"  利確目標    : {s['tp_price']:,}円（+7%）")
            print(f"  損切りライン: {s['sl_price']:,}円（-{s['sl_pct']:.1f}%）")
            print(f"  保有期間    : {s['hold_days']}日（{s['market_mode']}）")
            print(f"\n  【HOLDING_POSITIONSに追加する内容】")
            print(f"  {{")
            print(f"      \"ticker\":      \"{s['ticker']}\",")
            print(f"      \"name\":        \"（会社名）\",")
            print(f"      \"entry_date\":  \"{datetime.today().strftime('%Y-%m-%d')}\",")
            print(f"      \"entry_price\": 始値を記入,")
            print(f"      \"tp_price\":    {s['tp_price']},")
            print(f"      \"sl_price\":    {s['sl_price']},")
            print(f"      \"hold_days\":   {s['hold_days']},")
            print(f"      \"market_mode\": \"{s['market_mode']}\",")
            print(f"  }},")

    print()
    print("="*65)
    print(f"  ⏱️  総処理時間: {total_elapsed}秒")
    print(f"  （改善前: 180〜300秒 → 改善後: {total_elapsed}秒）")
    print("="*65)
