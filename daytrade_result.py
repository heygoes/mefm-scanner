# ============================================================
# デイトレード 結果スキャナー（11:30実行）
# 戦略C：前場の結果を計算してLINEで通知
# 紙トレード記録帳（HTMLファイル）に自動追記
#
# GitHub Actions で毎日11:30（JST）に実行
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

LINE_TOKEN                = os.environ.get("LINE_TOKEN", "")
LINE_USER_ID              = os.environ.get("LINE_USER_ID", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
COST_RATE = 0.002

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

def append_to_records(records):
    """紙トレード記録をJSONファイルに追記"""
    record_file = "daytrade_records.json"
    existing = []
    if os.path.exists(record_file):
        try:
            with open(record_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except: pass
    existing.extend(records)
    with open(record_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"記録保存: {record_file} ({len(existing)}件合計)")

def calc_monthly_stats(records):
    """月次集計"""
    if not records: return {}
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")
    result = {}
    for month, g in df.groupby("month"):
        wins = g[g["pnl_pct"] > 0]
        result[str(month)] = {
            "n": len(g),
            "wins": len(wins),
            "wr": round(len(wins)/len(g)*100, 1),
            "ev": round(g["pnl_pct"].mean(), 3),
            "total": round(g["pnl_pct"].sum(), 2),
        }
    return result

def main():
    today = datetime.now()
    if not is_weekday():
        print("土日スキップ"); return

    date_str  = today.strftime("%m/%d(%a)")
    today_str = today.strftime("%Y-%m-%d")
    print(f"デイトレ結果スキャン {date_str} 実行開始")

    # 本日のデータ取得（5分足）
    raw5m = {}
    for ticker in TICKERS:
        try:
            df5 = yf.download(ticker,
                start=(today - timedelta(days=2)).strftime("%Y-%m-%d"),
                end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval="5m", auto_adjust=True, progress=False)
            if isinstance(df5.columns, pd.MultiIndex):
                df5.columns = [c[0] for c in df5.columns]
            if len(df5) > 0:
                if df5.index.tz is not None:
                    df5.index = df5.index.tz_convert('Asia/Tokyo')
                else:
                    df5.index = df5.index.tz_localize('UTC').tz_convert('Asia/Tokyo')
                raw5m[ticker] = df5
        except: continue

    # 日足データ（5分足が取れない場合の補完）
    raw1d = yf.download(TICKERS,
        start=(today - timedelta(days=5)).strftime("%Y-%m-%d"),
        end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
        interval="1d", group_by="ticker",
        auto_adjust=True, progress=False, threads=True)

    print(f"5分足取得：{len(raw5m)}銘柄")

    # 戦略Cシグナル検出（本日の前場）
    results = []

    for ticker in TICKERS:
        # 5分足で前場を分析
        move_pct = None
        ep = None
        ex_p = None
        hit_sl = hit_tp = False
        data_src = "日足"

        if ticker in raw5m:
            df5 = raw5m[ticker]
            today_5m = df5[df5.index.date == today.date()]
            if len(today_5m) >= 5:
                morning = today_5m.between_time("09:00","09:55")
                after   = today_5m.between_time("10:00","11:30")

                if len(morning) >= 3 and len(after) >= 1:
                    open_p    = float(morning["Open"].iloc[0])
                    morning_h = float(morning["High"].max())
                    morning_l = float(morning["Low"].min())

                    if open_p > 0:
                        up_move   = (morning_h - open_p) / open_p * 100
                        down_move = (open_p - morning_l) / open_p * 100
                        data_src  = "5分足"

                        for direction, move, threshold in [
                            ("short", up_move,   2.0),
                            ("long",  down_move, 2.0),
                        ]:
                            if move < threshold: continue
                            if direction == "short":
                                ep   = morning_h
                                sl_p = ep * 1.007
                                tp_p = ep * 0.985
                            else:
                                ep   = morning_l
                                sl_p = ep * 0.993
                                tp_p = ep * 1.015

                            ex_p = float(after["Close"].iloc[-1])
                            hit_sl = hit_tp = False

                            for _, bar in after.iterrows():
                                hi = float(bar["High"]); lo = float(bar["Low"])
                                if direction == "short":
                                    if hi >= sl_p: ex_p=sl_p; hit_sl=True; break
                                    if lo <= tp_p: ex_p=tp_p; hit_tp=True; break
                                else:
                                    if lo <= sl_p: ex_p=sl_p; hit_sl=True; break
                                    if hi >= tp_p: ex_p=tp_p; hit_tp=True; break

                            pnl = ((ep-ex_p)/ep - COST_RATE) if direction=="short" \
                                  else ((ex_p-ep)/ep - COST_RATE)

                            move_pct   = move
                            exit_reason = "SL到達" if hit_sl else "TP到達" if hit_tp else "時間切れ(11:30)"

                            results.append({
                                "date":        today_str,
                                "ticker":      ticker,
                                "name":        get_name(ticker),
                                "direction":   direction,
                                "move_pct":    round(move, 2),
                                "ep":          round(ep, 0),
                                "ex_p":        round(ex_p, 0),
                                "pnl_pct":     round(pnl*100, 3),
                                "exit_reason": exit_reason,
                                "data_src":    data_src,
                                "strategy":    "C",
                            })

        # 5分足がない場合は日足で代替
        if ep is None:
            try:
                df1 = raw1d[ticker].dropna(how="all")
                if len(df1) < 2: continue
                today_idx = [i for i,d in enumerate(df1.index) if d.date()==today.date()]
                if not today_idx: continue
                idx = today_idx[0]
                cur_o = float(df1["Open"].iloc[idx])
                cur_h = float(df1["High"].iloc[idx])
                cur_l = float(df1["Low"].iloc[idx])
                cur_c = float(df1["Close"].iloc[idx])
                if cur_o <= 0: continue

                up_move   = (cur_h - cur_o) / cur_o * 100
                down_move = (cur_o - cur_l) / cur_o * 100

                for direction, move in [("short", up_move), ("long", down_move)]:
                    if move < 2.0: continue
                    ep_d = cur_h if direction=="short" else cur_l
                    sl_p = ep_d*1.007 if direction=="short" else ep_d*0.993
                    tp_p = ep_d*0.985 if direction=="short" else ep_d*1.015

                    hit_sl_d = (cur_h >= sl_p) if direction=="short" else (cur_l <= sl_p)
                    hit_tp_d = (cur_l <= tp_p) if direction=="short" else (cur_h >= tp_p)

                    if hit_sl_d: ex_p_d = sl_p
                    elif hit_tp_d: ex_p_d = tp_p
                    else: ex_p_d = cur_c

                    pnl_d = ((ep_d-ex_p_d)/ep_d - COST_RATE) if direction=="short" \
                            else ((ex_p_d-ep_d)/ep_d - COST_RATE)
                    exit_r = "SL到達" if hit_sl_d else "TP到達" if hit_tp_d else "時間切れ"

                    results.append({
                        "date":        today_str,
                        "ticker":      ticker,
                        "name":        get_name(ticker),
                        "direction":   direction,
                        "move_pct":    round(move, 2),
                        "ep":          round(ep_d, 0),
                        "ex_p":        round(ex_p_d, 0),
                        "pnl_pct":     round(pnl_d*100, 3),
                        "exit_reason": exit_r,
                        "data_src":    "日足代替",
                        "strategy":    "C",
                    })
            except: continue

    # 記録に追記
    if results:
        append_to_records(results)

    # 全記録を読んで月次集計
    record_file = "daytrade_records.json"
    all_records = []
    if os.path.exists(record_file):
        with open(record_file,"r",encoding="utf-8") as f:
            all_records = json.load(f)

    monthly = calc_monthly_stats(all_records)
    this_month = today.strftime("%Y-%m")
    this_month_stats = monthly.get(this_month, {})

    # LINEメッセージ
    wins   = [r for r in results if r["pnl_pct"] > 0]
    losses = [r for r in results if r["pnl_pct"] <= 0]

    lines = [
        f"📊 デイトレ結果 [{date_str}]",
        f"戦略C：{len(results)}件（✅{len(wins)}勝 ❌{len(losses)}敗）",
        "",
    ]

    # 勝ちトレード
    if wins:
        lines.append("【勝ちトレード】")
        for r in sorted(wins, key=lambda x: x["pnl_pct"], reverse=True):
            dir_label = "ショート↓" if r["direction"]=="short" else "ロング↑"
            lines.append(f"  ✅ {r['ticker']} {r['name']} {dir_label}")
            lines.append(f"     前場{r['move_pct']:+.1f}% → {r['exit_reason']}")
            lines.append(f"     {r['ep']:,}円→{r['ex_p']:,}円　{r['pnl_pct']:+.2f}%")

    lines.append("")

    # 負けトレード
    if losses:
        lines.append("【負けトレード】")
        for r in losses:
            dir_label = "ショート↓" if r["direction"]=="short" else "ロング↑"
            lines.append(f"  ❌ {r['ticker']} {r['name']} {dir_label}")
            lines.append(f"     前場{r['move_pct']:+.1f}% → {r['exit_reason']}")
            lines.append(f"     {r['ep']:,}円→{r['ex_p']:,}円　{r['pnl_pct']:+.2f}%")

    if not results:
        lines.append("本日は戦略Cのシグナルなし")

    # 今月の累計
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━")
    if this_month_stats:
        lines.append(f"【{this_month} 月次累計】")
        lines.append(f"  {this_month_stats['n']}件　"
                     f"勝率{this_month_stats['wr']}%　"
                     f"期待値{this_month_stats['ev']:+.2f}%")
        lines.append(f"  月間合計：{this_month_stats['total']:+.2f}%")
    else:
        lines.append("【今月の記録なし】")

    # 累計全期間
    if all_records:
        df_all = pd.DataFrame(all_records)
        total_n    = len(df_all)
        total_wr   = len(df_all[df_all["pnl_pct"]>0])/total_n*100
        total_ev   = df_all["pnl_pct"].mean()
        lines.append(f"【累計】{total_n}件　勝率{total_wr:.1f}%　期待値{total_ev:+.2f}%")

    lines.append("")
    lines.append("バックテスト基準：勝率81.6%・期待値+0.88%")

    msg = "\n".join(lines)
    print(msg)
    send_line(msg)
    print("\n結果スキャン完了")

main()
