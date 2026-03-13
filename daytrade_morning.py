# ============================================================
# デイトレード 朝スキャナー（8:50実行）
# 戦略C：前場候補を事前に把握してLINEで通知
#
# GitHub Actions で毎朝8:50（JST）に実行
# ============================================================

import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import os
import json
import warnings
warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "yfinance", "-q"])
    import yfinance as yf

LINE_TOKEN               = os.environ.get("LINE_TOKEN", "")
LINE_USER_ID             = os.environ.get("LINE_USER_ID", "")
LINE_CHANNEL_ACCESS_TOKEN= os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

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
    "9101.T":"日本郵船","9104.T":"商船三井","7974.T":"任天堂",
}

def get_name(t):
    return TICKER_NAME.get(t, t.replace(".T",""))

def send_line(msg):
    token = LINE_CHANNEL_ACCESS_TOKEN or LINE_TOKEN
    if not token:
        print("[LINE] トークン未設定"); return
    if LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID:
        try:
            requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={"Authorization":f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                         "Content-Type":"application/json"},
                json={"to":LINE_USER_ID,
                      "messages":[{"type":"text","text":msg}]}
            ); return
        except: pass
    requests.post(
        "https://notify-api.line.me/api/notify",
        headers={"Authorization":f"Bearer {LINE_TOKEN}"},
        data={"message":msg}
    )

def is_weekday():
    return datetime.now().weekday() < 5

def main():
    today = datetime.now()
    if not is_weekday():
        print("土日スキップ"); return

    date_str = today.strftime("%m/%d(%a)")
    print(f"デイトレ朝スキャン {date_str} 実行開始")

    # 直近5営業日の日足データ取得
    raw = yf.download(
        TICKERS,
        start=(today - timedelta(days=10)).strftime("%Y-%m-%d"),
        end=today.strftime("%Y-%m-%d"),
        interval="1d", group_by="ticker",
        auto_adjust=True, progress=False, threads=True
    )

    # 日経225
    nk = yf.download("^N225",
        start=(today - timedelta(days=10)).strftime("%Y-%m-%d"),
        end=today.strftime("%Y-%m-%d"),
        interval="1d", progress=False, auto_adjust=True)
    if isinstance(nk.columns, pd.MultiIndex):
        nk.columns = [c[0] for c in nk.columns]

    # 日経の直近動きを確認
    nk_ret = 0
    if len(nk) >= 2:
        nk_ret = (float(nk["Close"].iloc[-1]) - float(nk["Close"].iloc[-2])) \
                 / float(nk["Close"].iloc[-2]) * 100

    # 前日の大きな動きを検出（戦略Cの候補）
    # 「前日に大きく動いた銘柄は今日も動きやすい」
    candidates_short = []  # 前日大きく上昇 → 今日ショート候補
    candidates_long  = []  # 前日大きく下落 → 今日ロング候補

    for ticker in TICKERS:
        try:
            df = raw[ticker].dropna(how="all")
            if len(df) < 3: continue
        except: continue

        o = df["Open"]; c = df["Close"]
        h = df["High"]; l = df["Low"]
        v = df["Volume"]

        # 前日（直近確定日）のデータ
        prev_o   = float(o.iloc[-1])
        prev_c   = float(c.iloc[-1])
        prev_h   = float(h.iloc[-1])
        prev_l   = float(l.iloc[-1])
        prev_vol = float(v.iloc[-1])
        vol_avg  = float(v.iloc[-6:-1].mean()) if len(v) >= 6 else 0

        if prev_o <= 0: continue

        # 前日の前場上昇幅（寄り値→高値）
        up_move   = (prev_h - prev_o) / prev_o * 100
        down_move = (prev_o - prev_l) / prev_o * 100
        vol_ratio = prev_vol / vol_avg if vol_avg > 0 else 0

        # 前日+2%以上上昇 → 今日も同様の動きが出る可能性
        if up_move >= 2.0:
            candidates_short.append({
                "ticker": ticker,
                "name": get_name(ticker),
                "move": round(up_move, 1),
                "price": round(prev_c, 0),
                "vol_ratio": round(vol_ratio, 1),
            })

        if down_move >= 2.0:
            candidates_long.append({
                "ticker": ticker,
                "name": get_name(ticker),
                "move": round(down_move, 1),
                "price": round(prev_c, 0),
                "vol_ratio": round(vol_ratio, 1),
            })

    candidates_short.sort(key=lambda x: x["move"], reverse=True)
    candidates_long.sort(key=lambda x: x["move"], reverse=True)

    # 候補をJSONで保存（昼スキャナーが読み込む）
    candidates_data = {
        "date": today.strftime("%Y-%m-%d"),
        "nk_ret": round(nk_ret, 2),
        "short": candidates_short[:10],
        "long":  candidates_long[:10],
    }
    with open("daytrade_candidates.json", "w", encoding="utf-8") as f:
        json.dump(candidates_data, f, ensure_ascii=False, indent=2)
    print("候補データ保存: daytrade_candidates.json")

    # LINEメッセージ作成
    lines = [
        f"🌅 デイトレ朝スキャン [{date_str}]",
        f"日経前日比：{nk_ret:+.2f}%",
        "",
        "【戦略C 今日の注目銘柄】",
        "前場+2%以上で動いたらショート候補",
        "前場-2%以上で動いたらロング候補",
        "",
    ]

    if candidates_short:
        lines.append("📉 ショート候補（前日上昇が大きかった銘柄）")
        for s in candidates_short[:5]:
            lines.append(f"  {s['ticker']} {s['name']}")
            lines.append(f"  前日高値幅+{s['move']}%　現値{s['price']:,}円")
    else:
        lines.append("📉 ショート候補：なし")

    lines.append("")

    if candidates_long:
        lines.append("📈 ロング候補（前日下落が大きかった銘柄）")
        for s in candidates_long[:5]:
            lines.append(f"  {s['ticker']} {s['name']}")
            lines.append(f"  前日安値幅-{s['move']}%　現値{s['price']:,}円")
    else:
        lines.append("📈 ロング候補：なし")

    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━",
        "【戦略C エントリールール】",
        "前場（9〜9:55）に+2%以上上昇→9:55にショート",
        "前場（9〜9:55）に-2%以上下落→9:55にロング",
        "SL：なし　TP：なし　11:30強制決済（終値）",
        "※SLなしのため株数で損失管理すること",
        "",
        "11:30に結果通知します📊",
    ])

    msg = "\n".join(lines)
    print(msg)
    send_line(msg)
    print("\n朝スキャン完了")

main()

