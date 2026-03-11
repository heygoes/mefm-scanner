# ============================================================
# MEFM スキャナー v10
# 全戦略統合版（材料株フォロー追加・修正済み）
#
# 毎日スキャンする戦略
# ① MEFM A4（スイング）
# ② 決算プレイ候補（yfinance版）
# ③ 自社株買い候補（TDnetスクレイピング）
# ④ 52週高値ブレイク候補
# ⑤ 材料株フォロー（出来高5倍+5%→3日保有）
# ============================================================

import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

try:
    import google.colab
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

import os
LINE_TOKEN = os.environ.get("LINE_TOKEN", "")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "yfinance", "-q"])
    import yfinance as yf

# ============================================================
# マクロテーブル・セクター
# ============================================================
MACRO_TABLE = {
    "7011.T":"GO","7012.T":"GO","7013.T":"GO","6301.T":"GO","6326.T":"GO",
    "8306.T":"GO","8316.T":"GO","8411.T":"GO","8766.T":"GO","8750.T":"GO",
    "8601.T":"GO","8604.T":"GO","8593.T":"GO",
    "8035.T":"GO","6857.T":"GO","6920.T":"GO","6146.T":"GO","7735.T":"GO",
    "6981.T":"GO","6762.T":"GO","7741.T":"GO","6965.T":"GO",
    "9503.T":"GO","9502.T":"GO","9531.T":"GO",
    "5401.T":"GO","5411.T":"GO","5713.T":"GO","5714.T":"GO",
    "5803.T":"GO","5801.T":"GO",
    "8001.T":"GO","8002.T":"GO","8053.T":"GO","8058.T":"GO","8031.T":"GO",
    "9432.T":"CAUTION","9433.T":"CAUTION","9434.T":"CAUTION",
    "9983.T":"CAUTION","6098.T":"CAUTION","6367.T":"CAUTION",
    "6954.T":"CAUTION","6861.T":"CAUTION","6971.T":"CAUTION",
    "4502.T":"CAUTION","4503.T":"CAUTION","4568.T":"CAUTION",
    "2802.T":"CAUTION","2914.T":"CAUTION","4452.T":"CAUTION",
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
}

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
    "7974.T","8031.T","9434.T","6501.T","6146.T","7735.T",
    "7013.T","5801.T","6965.T","8593.T",
]))

TICKER_NAME = {
    "7011.T":"三菱重工","7012.T":"川崎重工","7013.T":"IHI",
    "6301.T":"小松製作所","6326.T":"クボタ",
    "8306.T":"三菱UFJ","8316.T":"三井住友FG","8411.T":"みずほFG",
    "8766.T":"東京海上","8750.T":"第一生命","8601.T":"大和証券",
    "8604.T":"野村HD","8593.T":"三菱HCキャピタル",
    "8035.T":"東京エレク","6857.T":"アドバンテスト","6920.T":"レーザーテック",
    "6146.T":"ディスコ","7735.T":"スクリーンHD","6981.T":"村田製作所",
    "6762.T":"TDK","7741.T":"HOYA","6965.T":"浜松ホトニクス",
    "9503.T":"関西電力","9502.T":"中部電力","9531.T":"東京ガス",
    "5401.T":"日本製鉄","5411.T":"JFEホールディングス",
    "5713.T":"住友金属鉱山","5714.T":"DOWA","5803.T":"フジクラ","5801.T":"古河電工",
    "8001.T":"伊藤忠","8002.T":"丸紅","8053.T":"住友商事",
    "8058.T":"三菱商事","8031.T":"三井物産",
    "6758.T":"ソニーG","9984.T":"ソフトバンクG","7203.T":"トヨタ",
    "4063.T":"信越化学","6861.T":"キーエンス","9433.T":"KDDI",
    "9432.T":"NTT","6954.T":"ファナック","6367.T":"ダイキン",
    "9101.T":"日本郵船","9104.T":"商船三井",
}

# ============================================================
# テクニカル指標
# ============================================================
def calc_atr(df, p=14):
    h,l,c = df["High"],df["Low"],df["Close"]
    tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    return tr.rolling(p).mean()

def calc_bbw(df, p=20):
    c = df["Close"]
    return (c.rolling(p).std()*2) / (c.rolling(p).mean()+1e-9)

def calc_adx(df, p=14):
    h,l,c = df["High"],df["Low"],df["Close"]
    tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    dm_p = (h-h.shift(1)).clip(lower=0)
    dm_n = (l.shift(1)-l).clip(lower=0)
    dm_p = dm_p.where(dm_p>dm_n,0)
    dm_n = dm_n.where(dm_n>dm_p,0)
    atr14 = tr.ewm(alpha=1/p,adjust=False).mean()
    di_p  = 100*dm_p.ewm(alpha=1/p,adjust=False).mean()/(atr14+1e-9)
    di_n  = 100*dm_n.ewm(alpha=1/p,adjust=False).mean()/(atr14+1e-9)
    dx    = 100*(di_p-di_n).abs()/(di_p+di_n+1e-9)
    return dx.ewm(alpha=1/p,adjust=False).mean()

def calc_rsi(df, p=14):
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/p,adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/p,adjust=False).mean()
    return 100 - 100/(1+gain/(loss+1e-9))

def is_weekday():
    return datetime.now().weekday() < 5

def get_name(ticker):
    return TICKER_NAME.get(ticker, ticker.replace(".T",""))

# ============================================================
# LINE通知
# ============================================================
def send_line(msg, token):
    if not token:
        print("[LINE] トークン未設定")
        return
    if LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID:
        try:
            requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={"to": LINE_USER_ID,
                      "messages": [{"type":"text","text":msg}]}
            )
            return
        except:
            pass
    requests.post(
        "https://notify-api.line.me/api/notify",
        headers={"Authorization": f"Bearer {token}"},
        data={"message": msg}
    )

# ============================================================
# ① MEFM A4 スキャン
# ============================================================
def scan_mefm(raw, nk_c):
    signals = []
    for ticker in TICKERS:
        try:
            df = raw[ticker].dropna(how="all")
            if len(df) < 200: continue
        except:
            continue
        atr=calc_atr(df); bbw=calc_bbw(df)
        adx=calc_adx(df); rsi=calc_rsi(df)
        c=df["Close"]; nk=nk_c.reindex(df.index,method="ffill")
        i=-1
        cur_c = float(c.iloc[i])
        ma5   = float(c.iloc[i-5:i].mean())
        ma20  = float(c.iloc[i-20:i].mean())
        ma60  = float(c.iloc[i-60:i].mean())
        ma100 = float(c.iloc[i-100:i].mean())
        atr_n = float(atr.iloc[i])
        atr_mx= float(atr.iloc[i-60:i].max())
        bbw_n = float(bbw.iloc[i])
        bbw_mx= float(bbw.iloc[i-60:i].max())
        mom60 = (cur_c-float(c.iloc[i-60]))/(float(c.iloc[i-60])+1e-9)
        dev   = (cur_c-ma20)/ma20
        rsi_n = float(rsi.iloc[i])
        adx_n = float(adx.iloc[i])
        nk_m20= float(nk.iloc[i-20:i].mean())
        nk_m60= float(nk.iloc[i-60:i].mean())
        if cur_c<=ma100: continue
        if not(ma5>ma20>ma60): continue
        if atr_mx<=0 or bbw_mx<=0: continue
        if (atr_n/atr_mx)>=0.65 or (bbw_n/bbw_mx)>=0.60: continue
        if mom60<0.05 or adx_n<20: continue
        if not(-0.06<=dev<=-0.003): continue
        if rsi_n<=55: continue
        if nk_m20<=nk_m60: continue
        macro  = MACRO_TABLE.get(ticker,"CAUTION")
        sector = SECTOR_NAME.get(ticker,"その他")
        signals.append({
            "ticker":ticker,"name":get_name(ticker),
            "macro":macro,"sector":sector,
            "price":round(cur_c,0),"tp":round(cur_c*1.07,0),
            "sl":round(cur_c-atr_n*1.5,0),
            "rsi":round(rsi_n,1),"dev":round(dev*100,1),
            "strategy":"MEFM",
        })
    return signals

# ============================================================
# ② 決算プレイ候補スキャン
# ============================================================
def scan_earnings_proxy(raw, nk_c):
    signals = []
    for ticker in TICKERS:
        macro = MACRO_TABLE.get(ticker,"CAUTION")
        if macro == "PASS": continue
        try:
            df = raw[ticker].dropna(how="all")
            if len(df) < 110: continue
        except:
            continue
        c=df["Close"]; vol=df["Volume"]
        i=-1
        cur_c   = float(c.iloc[i])
        c_3d    = float(c.iloc[i-3])
        ma100   = float(c.iloc[i-100:i].mean())
        vol_now = float(vol.iloc[i-1])
        vol_avg = float(vol.iloc[i-20:i-1].mean())
        if ma100<=0 or vol_avg<=0: continue
        if cur_c <= ma100: continue
        ret_3d = (cur_c - c_3d) / c_3d
        if ret_3d < 0.05: continue
        if vol_now < vol_avg * 2.0: continue
        sector = SECTOR_NAME.get(ticker,"その他")
        signals.append({
            "ticker":ticker,"name":get_name(ticker),
            "macro":macro,"sector":sector,
            "price":round(cur_c,0),
            "ret_3d":round(ret_3d*100,1),
            "vol_ratio":round(vol_now/vol_avg,1),
            "tp":round(cur_c*1.07,0),"sl":None,
            "strategy":"決算プレイ候補",
            "note":"★TDnetで上方修正を要確認",
        })
    return signals

# ============================================================
# ③ 自社株買い候補スキャン
# ============================================================
def scan_buyback():
    signals = []
    try:
        url = "https://www.release.tdnet.info/inbs/I_list_001_99999.html"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return signals
        from html.parser import HTMLParser
        class TDnetParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results=[]; self.current={}
                self.in_td=False; self.td_count=0; self.in_row=False
            def handle_starttag(self, tag, attrs):
                if tag=="tr":
                    self.in_row=True; self.current={}; self.td_count=0
                if tag=="td" and self.in_row:
                    self.in_td=True
            def handle_endtag(self, tag):
                if tag=="td":
                    self.in_td=False; self.td_count+=1
                if tag=="tr" and self.in_row:
                    self.in_row=False
                    if self.current.get("title"):
                        self.results.append(dict(self.current))
            def handle_data(self, data):
                data=data.strip()
                if not data or not self.in_td: return
                if self.td_count==0: self.current["time"]=data
                elif self.td_count==1: self.current["code"]=data
                elif self.td_count==2: self.current["company"]=data
                elif self.td_count==3: self.current["title"]=data
        parser = TDnetParser()
        parser.feed(resp.text)
        keywords = ["自己株式","自社株","株式取得","取得開始"]
        for item in parser.results:
            title = item.get("title","")
            if any(kw in title for kw in keywords):
                code = item.get("code","").strip()
                if code and len(code)==4:
                    ticker = f"{code}.T"
                    macro  = MACRO_TABLE.get(ticker,"CAUTION")
                    if macro == "PASS": continue
                    signals.append({
                        "ticker":ticker,"name":get_name(ticker),
                        "macro":macro,
                        "sector":SECTOR_NAME.get(ticker,"その他"),
                        "price":None,"title":title[:30],
                        "tp":None,"sl":None,
                        "strategy":"自社株買い",
                        "note":"翌日寄り買い・15日保有",
                    })
    except Exception as e:
        print(f"[自社株買いスキャン] エラー: {e}")
    return signals

# ============================================================
# ④ 52週高値ブレイク候補スキャン
# ============================================================
def scan_52week(raw, nk_c):
    signals = []
    nk_m20 = float(nk_c.iloc[-20:].mean())
    nk_m60 = float(nk_c.iloc[-60:].mean())
    if nk_m20 <= nk_m60:
        return signals
    for ticker in TICKERS:
        macro = MACRO_TABLE.get(ticker,"CAUTION")
        if macro == "PASS": continue
        try:
            df = raw[ticker].dropna(how="all")
            if len(df) < 260: continue
        except:
            continue
        c=df["Close"]; vol=df["Volume"]
        i=-1
        cur_c   = float(c.iloc[i])
        high_52 = float(c.iloc[i-252:i-1].max())
        vol_now = float(vol.iloc[i-1])
        vol_avg = float(vol.iloc[i-20:i-1].mean())
        if vol_avg <= 0: continue
        if cur_c <= high_52: continue
        if vol_now < vol_avg * 1.2: continue
        breakout_pct = (cur_c - high_52) / high_52 * 100
        sector = SECTOR_NAME.get(ticker,"その他")
        signals.append({
            "ticker":ticker,"name":get_name(ticker),
            "macro":macro,"sector":sector,
            "price":round(cur_c,0),"high_52":round(high_52,0),
            "breakout":round(breakout_pct,1),
            "vol_ratio":round(vol_now/vol_avg,1),
            "tp":round(cur_c*1.07,0),"sl":round(cur_c*0.93,0),
            "strategy":"52週高値",
            "note":f"52週高値{round(high_52,0)}を更新",
        })
    return sorted(signals, key=lambda x: x["breakout"], reverse=True)

# ============================================================
# ⑤ 材料株フォロー スキャン
# ============================================================
def scan_material(raw, nk_c):
    signals = []
    nk_m20 = float(nk_c.iloc[-20:].mean())
    nk_m60 = float(nk_c.iloc[-60:].mean())
    if nk_m20 <= nk_m60:
        return signals
    for ticker in TICKERS:
        macro = MACRO_TABLE.get(ticker,"CAUTION")
        if macro == "PASS": continue
        try:
            df = raw[ticker].dropna(how="all")
            if len(df) < 25: continue
        except:
            continue
        c=df["Close"]; v=df["Volume"]
        i=-1
        vol_avg = float(v.iloc[i-20:i-1].mean())
        vol_now = float(v.iloc[i-1])
        if vol_avg <= 0: continue
        if vol_now < vol_avg * 5.0: continue
        cur_c  = float(c.iloc[i-1])
        prev_c = float(c.iloc[i-2])
        if prev_c <= 0: continue
        ret = (cur_c - prev_c) / prev_c
        if ret < 0.05: continue
        sector = SECTOR_NAME.get(ticker,"その他")
        signals.append({
            "ticker":ticker,"name":get_name(ticker),
            "macro":macro,"sector":sector,
            "price":round(cur_c,0),
            "ret":round(ret*100,1),
            "vol_ratio":round(vol_now/vol_avg,1),
            "tp":round(cur_c*1.10,0),"sl":round(cur_c*0.93,0),
            "strategy":"材料株",
            "note":f"出来高{round(vol_now/vol_avg,1)}倍・当日+{round(ret*100,1)}%・3日保有",
        })
    return sorted(signals, key=lambda x: x["vol_ratio"], reverse=True)

# ============================================================
# 相場判断
# ============================================================
def get_market_condition(nk_c):
    nk_now = float(nk_c.iloc[-1])
    nk_m20 = float(nk_c.iloc[-20:].mean())
    nk_m60 = float(nk_c.iloc[-60:].mean())
    ret_20 = (nk_now - float(nk_c.iloc[-20])) / float(nk_c.iloc[-20]) * 100
    if nk_m20 > nk_m60 and ret_20 > 3:
        return "強い上昇"
    elif nk_m20 > nk_m60:
        return "普通の上昇"
    elif ret_20 < -10:
        return "⚠️暴落注意"
    else:
        return "下降トレンド"

# ============================================================
# LINE通知メッセージ生成
# ============================================================
def build_message(today, market, mefm, earnings, buyback, w52, material):
    date_str = today.strftime("%m/%d(%a)")
    lines = [f"📊 MEFM v10 [{date_str}]", f"相場：{market}", ""]

    # ① MEFM
    mefm_go = [s for s in mefm if s["macro"]=="GO"]
    if mefm_go:
        lines.append(f"【MEFM】{len(mefm_go)}件 ✅")
        for s in mefm_go[:3]:
            lines.append(f"  {s['ticker']} {s['name']}")
            lines.append(f"  現値:{s['price']} TP:{s['tp']} SL:{s['sl']}")
    else:
        lines.append("【MEFM】シグナルなし")
    lines.append("")

    # ② 決算プレイ
    if earnings:
        lines.append(f"【決算プレイ候補】{len(earnings)}件 📈")
        for s in earnings[:3]:
            lines.append(f"  {s['ticker']} {s['name']}")
            lines.append(f"  3日+{s['ret_3d']}% 出来高{s['vol_ratio']}倍")
            lines.append(f"  ★TDnetで上方修正を確認")
    else:
        lines.append("【決算プレイ候補】なし")
    lines.append("")

    # ③ 自社株買い
    if buyback:
        lines.append(f"【自社株買い】{len(buyback)}件 🔄")
        for s in buyback[:3]:
            lines.append(f"  {s['ticker']} {s['name']}")
            lines.append(f"  {s['title']}")
    else:
        lines.append("【自社株買い】発表なし")
    lines.append("")

    # ④ 52週高値
    if w52:
        lines.append(f"【52週高値ブレイク】{len(w52)}件 🚀")
        for s in w52[:3]:
            lines.append(f"  {s['ticker']} {s['name']}")
            lines.append(f"  現値:{s['price']} ブレイク+{s['breakout']}%")
    else:
        lines.append("【52週高値】なし")
    lines.append("")

    # ⑤ 材料株
    if material:
        lines.append(f"【材料株フォロー】{len(material)}件 🔥")
        for s in material[:3]:
            lines.append(f"  {s['ticker']} {s['name']}")
            lines.append(f"  当日+{s['ret']}% 出来高{s['vol_ratio']}倍")
            lines.append(f"  翌日寄り買い・3日保有 SL:{s['sl']}")
    else:
        lines.append("【材料株フォロー】なし")
    lines.append("")

    total = len(mefm_go)+len(earnings)+len(buyback)+len(w52)+len(material)
    lines.append(f"合計候補：{total}件")
    lines.append("→紙トレード記録帳に入力してください")

    return "\n".join(lines)

# ============================================================
# メイン実行
# ============================================================
def main():
    today = datetime.now()
    print(f"MEFM v10 全戦略統合スキャナー")
    print(f"実行: {today.strftime('%Y-%m-%d %H:%M')}")

    if not is_weekday():
        msg = f"\n📊 MEFM v10\n{today.strftime('%m/%d')} 土日のためスキャンをスキップ"
        print(msg)
        send_line(msg, LINE_CHANNEL_ACCESS_TOKEN or LINE_TOKEN)
        return

    print("データ取得中...")
    raw = yf.download(TICKERS, period="2y", interval="1d",
                      group_by="ticker", auto_adjust=True,
                      progress=False, threads=True)
    nk_raw = yf.download("^N225", period="2y", interval="1d",
                         progress=False, auto_adjust=True)
    if isinstance(nk_raw.columns, pd.MultiIndex):
        nk_raw.columns = [c[0] for c in nk_raw.columns]
    nk_c = nk_raw["Close"]
    print("完了")

    market   = get_market_condition(nk_c)
    mefm     = scan_mefm(raw, nk_c)
    earnings = scan_earnings_proxy(raw, nk_c)
    buyback  = scan_buyback()
    w52      = scan_52week(raw, nk_c)
    material = scan_material(raw, nk_c)

    mefm_go = [s for s in mefm if s["macro"]=="GO"]

    print(f"\n{'='*55}")
    print(f"  相場：{market}")
    print(f"{'='*55}")
    print(f"  MEFM GOシグナル    : {len(mefm_go)}件")
    print(f"  決算プレイ候補     : {len(earnings)}件（TDnet確認要）")
    print(f"  自社株買い         : {len(buyback)}件")
    print(f"  52週高値ブレイク   : {len(w52)}件")
    print(f"  材料株フォロー     : {len(material)}件")
    print(f"{'='*55}")

    if mefm_go:
        print("\n[MEFM GOシグナル]")
        for s in mefm_go:
            print(f"  {s['ticker']} {s['name']}({s['sector']})"
                  f" 現値:{s['price']} TP:{s['tp']} SL:{s['sl']}"
                  f" RSI:{s['rsi']} 乖離:{s['dev']}%")

    if earnings:
        print("\n[決算プレイ候補]（TDnetで上方修正を確認）")
        for s in earnings:
            print(f"  {s['ticker']} {s['name']}"
                  f" 3日+{s['ret_3d']}% 出来高{s['vol_ratio']}倍"
                  f" 現値:{s['price']}")

    if buyback:
        print("\n[自社株買い候補]")
        for s in buyback:
            print(f"  {s['ticker']} {s['name']} - {s['title']}")

    if w52:
        print("\n[52週高値ブレイク候補]")
        for s in w52:
            print(f"  {s['ticker']} {s['name']}"
                  f" 現値:{s['price']} ブレイク+{s['breakout']}%"
                  f" 出来高{s['vol_ratio']}倍")

    if material:
        print("\n[材料株フォロー候補]（翌日寄り買い・3日保有）")
        for s in material:
            print(f"  {s['ticker']} {s['name']}"
                  f" 当日+{s['ret']}% 出来高{s['vol_ratio']}倍"
                  f" 現値:{s['price']} SL:{s['sl']}")

    total = len(mefm_go)+len(earnings)+len(buyback)+len(w52)+len(material)
    if total == 0:
        print("\n本日は全戦略でシグナルなし → 待機")

    msg = build_message(today, market, mefm, earnings, buyback, w52, material)
    send_line(msg, LINE_CHANNEL_ACCESS_TOKEN or LINE_TOKEN)
    print("\nLINE通知送信完了")

main()
