# ============================================================
# MEFM-Pro デイリースキャナー v6c（GitHub Actions + Colab 共用版）
# 毎営業日の夜（15時以降）に実行
#
# v6c条件：
#   エントリー条件 → v6aと同一（7ステップ + RSI>50）
#   保有期間       → 動的切替
#     強い上昇（日経終値 > 20MA）→ 20日
#     普通の上昇（日経終値 < 20MA）→ 15日
#   TP: +7% / SL: ATR×1.5
#
# 機能①：新規買いシグナル検出
# 機能②：保有中ポジションの売りタイミング判定
# 機能③：LINE通知（Messaging API）
# 機能④：GitHub Actions / Colab 自動判定
# ============================================================

import os
import sys
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# 実行環境の自動判定
# ============================================================

def is_colab():
    try:
        import google.colab
        return True
    except ImportError:
        return False

RUNNING_ON_COLAB = is_colab()

if RUNNING_ON_COLAB:
    print("🖥️  実行環境: Google Colab")
else:
    print("⚙️  実行環境: GitHub Actions")

# ============================================================
# LINE設定（環境に応じて自動切替）
# ============================================================

if RUNNING_ON_COLAB:
    # ── Colab用：ここに直接貼り付け ──────────────────────
    LINE_TOKEN = "ここにChannel_Access_Tokenを貼り付け"
    USER_ID    = "ここにUSER_IDを貼り付け"
    # ────────────────────────────────────────────────────────
else:
    # GitHub Actions用：Secretsから自動取得
    LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    USER_ID    = os.getenv("LINE_USER_ID")

# ============================================================
# 休場日チェック
# ============================================================

def check_market_day():
    """土日・休場日の判定と警告"""
    today = datetime.today()
    weekday = today.weekday()  # 0=月曜 〜 6=日曜

    if weekday >= 5:  # 土日
        day_name = "土曜日" if weekday == 5 else "日曜日"
        print(f"⚠️  本日は{day_name}です（市場休場）")
        print(f"   直近の確定データ（金曜終値）でスキャンします。")
        print(f"   シグナルが出た場合は月曜朝に再確認してから買ってください。")
        print()
        return False  # 休場
    return True  # 営業日

# ============================================================
# ★保有中のポジションをここに入力★
# 買ったら追加・売ったら削除
# ============================================================
HOLDING_POSITIONS = [
    # 例：
    # {
    #     "ticker":      "7203.T",
    #     "name":        "トヨタ",
    #     "entry_date":  "2025-09-17",
    #     "entry_price": 2856,
    #     "tp_price":    3056,
    #     "sl_price":    2785,
    #     "hold_days":   20,
    #     "market_mode": "強い上昇",
    # },
]
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

END      = datetime.today().strftime("%Y-%m-%d")
START    = (datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d")
NK_START = (datetime.today() - timedelta(days=500)).strftime("%Y-%m-%d")

# ============================================================
# 指標計算
# ============================================================

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

def business_days_between(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")
    days  = 0; cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return max(0, days - 1)

# ============================================================
# LINE通知（Messaging API）
# ============================================================

def send_line(message):
    if not LINE_TOKEN or not USER_ID:
        print("  ⚠️  LINE未設定・スキップ")
        if RUNNING_ON_COLAB:
            print("     → Colab版：LINE_TOKEN と USER_ID を直接貼り付けてください")
        else:
            print("     → GitHub版：Secrets に LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID を登録してください")
        return
    # Colabで設定例文のままの場合はスキップ
    if "ここに" in LINE_TOKEN or "ここに" in USER_ID:
        print("  ⚠️  LINE未設定（サンプル文のまま）・スキップ")
        return
    try:
        r = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_TOKEN}"
            },
            json={
                "to": USER_ID,
                "messages": [{"type": "text", "text": message[:5000]}]
            },
            timeout=10
        )
        if r.status_code == 200:
            print("  ✅ LINE送信完了")
        else:
            print(f"  ❌ LINE送信失敗: {r.status_code} {r.text}")
    except Exception as e:
        print(f"  ❌ LINE送信エラー: {e}")

# ============================================================
# 売りタイミング判定
# ============================================================

def check_sell(positions):
    if not positions:
        return []
    print("="*65)
    print("  📤 保有ポジション・売りタイミングチェック")
    print("="*65)
    sell_alerts = []
    for pos in positions:
        try:
            df=yf.download(pos["ticker"], start=pos["entry_date"], end=END,
                           interval="1d", progress=False, auto_adjust=True)
            if isinstance(df.columns,pd.MultiIndex): df.columns=[col[0] for col in df.columns]
            if df.empty: print(f"\n  ⚠️  {pos['name']}: データ取得失敗"); continue

            cur_price = float(df["Close"].iloc[-1])
            cur_high  = float(df["High"].iloc[-1])
            cur_low   = float(df["Low"].iloc[-1])
            cur_date  = str(df.index[-1].date())
            held      = business_days_between(pos["entry_date"], cur_date)
            days_left = pos["hold_days"] - held
            pnl       = (cur_price - pos["entry_price"]) / pos["entry_price"] * 100

            print(f"\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"  📌 {pos['name']}（{pos['ticker']}）{pos['market_mode']}")
            print(f"  買値    : {pos['entry_price']:,}円")
            print(f"  現在値  : {cur_price:,.0f}円  （{pnl:+.2f}%）")
            print(f"  利確目標: {pos['tp_price']:,}円  （あと{pos['tp_price']-cur_price:+.0f}円）")
            print(f"  損切り  : {pos['sl_price']:,}円  （あと{cur_price-pos['sl_price']:+.0f}円）")
            print(f"  保有    : {held}日経過 / {pos['hold_days']}日（残り{days_left}日）")
            print()

            alert = None
            if cur_high >= pos["tp_price"]:
                print(f"  🎯【利確タイミング】本日高値が利確目標に到達")
                print(f"     → 本日または明日の寄り付きで売ってください")
                alert = f"🎯 利確タイミング\n{pos['name']}({pos['ticker']})\n現在値{cur_price:,.0f}円 → 利確目標{pos['tp_price']:,}円到達"
            elif cur_low <= pos["sl_price"]:
                print(f"  🚨【損切りタイミング】安値が損切りラインを下回りました")
                print(f"     → 逆指値が機能していれば自動決済済み")
                alert = f"🚨 損切りタイミング\n{pos['name']}({pos['ticker']})\n安値{cur_low:,.0f}円 → 損切りライン{pos['sl_price']:,}円割れ"
            elif days_left <= 0:
                print(f"  ⏰【期間満了】保有{pos['hold_days']}日が経過 → 明日の寄り付きで売り")
                print(f"     現在損益: {pnl:+.2f}%")
                alert = f"⏰ 期間満了\n{pos['name']}({pos['ticker']})\n{pos['hold_days']}日経過 → 明日売り\n損益{pnl:+.2f}%"
            elif days_left == 1:
                print(f"  ⚠️  明日が最終保有日 → 明日終値で売り  損益: {pnl:+.2f}%")
                alert = f"⚠️ 明日が最終保有日\n{pos['name']}({pos['ticker']})\n損益{pnl:+.2f}%"
            else:
                emoji = "✅" if pnl > 0 else "⚠️"
                print(f"  {emoji} 保有継続（含み{'益' if pnl>0 else '損'} {pnl:+.2f}%）残り{days_left}日")

            if alert:
                sell_alerts.append(alert)

        except Exception as e:
            print(f"\n  ⚠️  {pos.get('name','?')}: エラー {e}")
    print()
    return sell_alerts

# ============================================================
# 買いシグナルスキャン
# ============================================================

def scan_buy(ticker, nk_close, hold_days, market_mode):
    try:
        df=yf.download(ticker, start=START, end=END,
                       interval="1d", progress=False, auto_adjust=True)
        if len(df)<120: return None
        if isinstance(df.columns,pd.MultiIndex): df.columns=[col[0] for col in df.columns]

        atr=calc_atr(df); bbw=calc_bbw(df); adx=calc_adx(df); rsi=calc_rsi(df)
        c=df["Close"]; nk=nk_close.reindex(df.index,method="ffill")
        i=len(df)-1
        if i<110: return None

        # STEP1: 100MA上
        if c.iloc[i]<=c.iloc[i-100:i].mean(): return None
        # STEP2: 5MA > 20MA > 60MA
        ma5=c.iloc[i-5:i].mean(); ma20=c.iloc[i-20:i].mean(); ma60=c.iloc[i-60:i].mean()
        if not(ma5>ma20>ma60): return None
        # STEP3: ATR・BB幅の収縮（エネルギー蓄積）
        atr_now=atr.iloc[i]; atr_max=atr.iloc[max(0,i-60):i].max()
        bbw_now=bbw.iloc[i]; bbw_max=bbw.iloc[max(0,i-60):i].max()
        if atr_max<=0 or bbw_max<=0: return None
        if(atr_now/atr_max)>=0.65 or(bbw_now/bbw_max)>=0.60: return None
        # STEP4: モメンタム + ADX
        mom60=(c.iloc[i]-c.iloc[i-60])/(c.iloc[i-60]+1e-9)
        if mom60<0.05 or adx.iloc[i]<20: return None
        # STEP5: 押し目 -0.3%〜-6%
        deviation=(c.iloc[i]-ma20)/ma20
        if not(-0.06<=deviation<=-0.003): return None
        # STEP6: 本日終値 > 前日高値（反発確認）
        if i<1: return None
        if c.iloc[i]<=df["High"].iloc[i-1]: return None
        # RSI > 50
        if rsi.iloc[i]<=50: return None
        # STEP7: 日経20MA > 60MA
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
            "prev_high":   int(round(float(df["High"].iloc[i-1]))),
            "atr":         round(atr_val, 1),
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

# ============================================================
# メイン実行
# ============================================================

today_str  = datetime.today().strftime("%Y年%m月%d日")
is_weekday = check_market_day()

print(f"MEFM-Pro スキャナー v6c  {today_str}")
if not is_weekday:
    print("（土日実行：金曜終値データでスキャン。シグナルは月曜朝に再確認）")
print()

print("日経データ取得中...")
nk_raw=yf.download("^N225", start=NK_START, end=END,
                   interval="1d", progress=False, auto_adjust=True)
if isinstance(nk_raw.columns,pd.MultiIndex): nk_raw.columns=[col[0] for col in nk_raw.columns]
nk_close=nk_raw["Close"]
nk_date = str(nk_raw.index[-1].date())
print(f"取得完了（最新データ日付：{nk_date}）\n")

nk_i       = len(nk_close)-1
nk_price   = float(nk_close.iloc[nk_i])
nk_ma20    = float(nk_close.iloc[nk_i-20:nk_i].mean())
nk_ma60    = float(nk_close.iloc[nk_i-60:nk_i].mean())
nk_ok      = nk_ma20 > nk_ma60
hold_days, market_mode = get_hold_days(nk_close, nk_i)

print("="*65)
print("  📈 市場環境（STEP7 + v6c保有期間判定）")
print("="*65)
print(f"  データ日 : {nk_date}")
print(f"  日経終値 : {nk_price:>10,.0f}円")
print(f"  20MA     : {nk_ma20:>10,.0f}円")
print(f"  60MA     : {nk_ma60:>10,.0f}円")
print(f"  STEP7    : {'✅ 上昇トレンド（エントリー可）' if nk_ok else '❌ 下落/レンジ（エントリー見送り）'}")
if nk_ok:
    print(f"  相場モード: {market_mode}")
    print(f"  保有期間  : {hold_days}日")
    if hold_days == 20:
        print(f"  （日経終値{nk_price:,.0f}円 > 20MA{nk_ma20:,.0f}円 → 強い上昇🔥）")
    else:
        print(f"  （日経終値{nk_price:,.0f}円 < 20MA{nk_ma20:,.0f}円 → 普通の上昇）")
print()

# 売りチェック
sell_alerts = check_sell(HOLDING_POSITIONS)

# 買いスキャン
signals = []
if not nk_ok:
    print("="*65)
    print("  ⚠️  本日はエントリー条件外（日経フィルターNG）")
    print("  保有ポジションの管理のみ行ってください。")
    print("="*65)
else:
    print("="*65)
    print(f"  🔍 買いシグナルスキャン中（{len(TICKERS)}銘柄）...")
    print("="*65)
    for ticker in TICKERS:
        result=scan_buy(ticker, nk_close, hold_days, market_mode)
        if result:
            signals.append(result)

    print()
    if not signals:
        print("  📭 本日の買いシグナル：なし")
        print("  明日また実行してください。")
    else:
        print(f"  🔔 本日の買いシグナル：{len(signals)}銘柄")
        print()
        for s in signals:
            print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"  📌 {s['ticker']}")
            print(f"  本日終値    : {s['close']:,}円")
            print(f"  前日高値    : {s['prev_high']:,}円  ← 翌朝この値を超えたら買い")
            print(f"  RSI         : {s['rsi']:.1f}")
            print(f"  押し目      : {s['deviation']:+.2f}%")
            print(f"  ATR         : {s['atr']:.1f}円")
            print()
            print(f"  【エントリー情報（v6c・{market_mode}）】")
            print(f"  保有期間    : {s['hold_days']}日")
            print(f"  利確目標    : {s['tp_price']:,}円（+7%）")
            print(f"  損切りライン: {s['sl_price']:,}円（-{s['sl_pct']:.1f}%）")
            print()
            print(f"  【買ったらHOLDING_POSITIONSに追加する内容】")
            print(f"  {{")
            print(f"      \"ticker\":      \"{s['ticker']}\",")
            print(f"      \"name\":        \"（会社名を記入）\",")
            print(f"      \"entry_date\":  \"{datetime.today().strftime('%Y-%m-%d')}\",")
            print(f"      \"entry_price\": 始値を記入,")
            print(f"      \"tp_price\":    {s['tp_price']},")
            print(f"      \"sl_price\":    {s['sl_price']},")
            print(f"      \"hold_days\":   {s['hold_days']},")
            print(f"      \"market_mode\": \"{market_mode}\",")
            print(f"  }},")

        print()
        print("="*65)
        print("  📋 翌朝の手順")
        print("="*65)
        print("  1. 9:00〜9:30に上記銘柄の始値を確認")
        print("  2. 始値が「前日高値」を超えていればS株で買う")
        print("  3. 買ったら即座に逆指値（損切りライン）を入れる")
        print(f"  4. HOLDING_POSITIONSに追加（保有期間：{hold_days}日）")
        print()
        print("  ⚠️  前日高値を超えていなければ買わない")
        print("  ⚠️  土日シグナルは月曜朝に再確認してから買う")
        print("  ⚠️  投資は自己責任で")
        print("="*65)

print(f"\n  実行完了: {datetime.today().strftime('%Y-%m-%d %H:%M')}")

# ============================================================
# LINE通知
# ============================================================

print("\n" + "="*65)
print("  📨 LINE通知送信中...")
print("="*65)

weekend_note = "\n⚠️土日データ：月曜朝に再確認してから買う" if not is_weekday else ""

# 売りアラートがあれば先に送信
if sell_alerts:
    sell_text = f"📤 MEFM保有ポジションアラート {today_str}\n\n"
    sell_text += "\n\n".join(sell_alerts)
    send_line(sell_text)

# 買いシグナル通知
if not nk_ok:
    send_line(
        f"⚠️ MEFM {today_str}\n"
        f"日経フィルターNG\n"
        f"20MA {nk_ma20:,.0f} < 60MA {nk_ma60:,.0f}\n"
        f"本日はエントリー見送り"
        f"{weekend_note}"
    )
elif not signals:
    send_line(
        f"📭 MEFM {today_str}\n"
        f"本日のシグナル：なし\n"
        f"相場：{market_mode}"
        f"{weekend_note}"
    )
else:
    text  = f"📈 MEFMシグナル {today_str}\n"
    text += f"検出：{len(signals)}銘柄  相場：{market_mode}\n"
    text += "─" * 20 + "\n\n"
    for s in signals:
        text += (
            f"📌 {s['ticker']}\n"
            f"終値      {s['close']:,}円\n"
            f"買いライン {s['prev_high']:,}円超えで買い\n"
            f"利確目標  {s['tp_price']:,}円 (+7%)\n"
            f"損切り    {s['sl_price']:,}円 (-{s['sl_pct']}%)\n"
            f"保有期間  {s['hold_days']}日\n\n"
        )
    text += "※翌朝寄り付きで買いライン超えを確認してから買う\n"
    text += "※投資は自己責任で"
    text += weekend_note
    send_line(text)
