# ============================================================
# TDnet適時開示 監視スキャナー（本番版 v1.1）
#
# 変更履歴：
#   v1.1 2026-07-07
#     ・公式TDnet HTML直取得を第一系統に変更
#       （yanoshin APIタイムアウト頻発のため予備に降格）
#     ・経過報告系ノイズを除外
#       （取得状況・の結果・取得終了など）
#
# 実行スケジュール（GitHub Actions）：
#   20:30 JST 夜間スキャン（引け後の開示を検知）← 最重要
#   07:40 JST 朝スキャン（夜間・早朝の開示を検知）
#
# 通知：LINE（既存のMEFMスキャナーと同じ仕組み）
# 重複防止：tdnet_seen.json をリポジトリにコミット
# ============================================================

import requests
import json
import re
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
SEEN_FILE = "tdnet_seen.json"

# ============================================================
# LINE通知設定
# ※既存スキャナー（mefm_scanner_v10.py）と同じ
#   環境変数・送信方式を使用してください。
#   下の send_line() を既存の送信関数に合わせて
#   置き換えれば完了です。
# ============================================================
LINE_TOKEN   = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")

def send_line(message):
    """LINE Messaging API push送信（既存方式に合わせて要調整）"""
    if not LINE_TOKEN or not LINE_USER_ID:
        print("[LINE未設定のためコンソール出力]")
        print(message)
        return
    try:
        r = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_TOKEN}",
            },
            json={
                "to": LINE_USER_ID,
                "messages": [{"type": "text", "text": message[:4900]}],
            },
            timeout=30,
        )
        print(f"LINE送信：{r.status_code}")
    except Exception as e:
        print(f"LINE送信エラー：{e}")

# ============================================================
# コア監視銘柄（MEFM v10と同じ92銘柄・4桁コード）
# ============================================================
CORE_CODES = {
    "7012","7011","6861","6857","6762","6758","6701","6702","6954","6971",
    "5803","5401","4502","4503","4523","4063","4188","4452","3382","2802",
    "9984","9983","9432","9433","8306","8316","8411","8035","7203","7267",
    "6367","6301","6326","4661","3659","3923","4385","4478","6098","9101",
    "9104","8001","8002","8053","8058","8601","8604","8766","8750","9502",
    "9503","9531","9020","9021","9022","5713","5714","4568","4519","4527",
    "6902","6920","6981","7751","7741","7201","7202","7205","6503","6504",
    "6506","5411","3407","3401","1801","1802","1928","8801","8802","4689",
    "4755","4751","2269","2502","2914","9301","9202","4543","6869","4307",
    "4324","9719","7974","8031","9434","6501","6146","7735","7013","5801",
    "6965","8593",
}

# ============================================================
# キーワードスコア定義
# ============================================================
KEYWORD_SCORES = {
    "資本業務提携": 5, "TOB": 5, "公開買付": 5, "MBO": 5, "経営統合": 5,
    "資本提携": 4, "合併": 4, "自己株式の取得": 4, "自社株買い": 4,
    "上方修正": 4, "戦略的提携": 4,
    "業務提携": 3, "増配": 3, "株式分割": 3, "特別配当": 3,
    "過去最高": 3, "大型受注": 3,
    "記念配当": 2, "新工場": 2, "業績予想の修正": 2,
}

# 除外キーワード（v1.1でノイズ対策を強化）
EXCLUDE_KEYWORDS = [
    "訂正", "消却", "立会外", "下方修正", "特別損失", "減配",
    "定款", "人事", "役員", "株主総会", "招集",
    # ─ 経過報告系（新材料ではない・7/7の実地検証で確認）─
    "取得状況",       # 自社株買いの月次経過報告
    "の結果",         # TOB結果・買付結果
    "取得終了",
    "買付けの結果",
    "異動に関する",   # 結果に伴う異動報告
]

# ============================================================
# 重複防止
# ============================================================
def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_seen(seen):
    # 直近2000件のみ保持（肥大化防止）
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-2000:], f)

# ============================================================
# TDnet取得（第一系統：公式HTML／予備：yanoshin API）
# ============================================================
def fetch_tdnet_official():
    """公式TDnetの当日開示一覧HTMLを直接取得（第一系統）"""
    day = datetime.now(JST).strftime("%Y%m%d")
    results = []
    for page in ["001", "002", "003", "004", "005"]:
        url = f"https://www.release.tdnet.info/inbs/I_list_{page}_{day}.html"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                break
            html = r.content.decode("utf-8", errors="ignore")
            rows = re.findall(
                r'kjCode[^>]*>(\d{4})\d?</td>.*?kjName[^>]*>(.*?)</td>.*?<a[^>]*>(.*?)</a>',
                html, re.S)
            if not rows:
                break
            for code, name, title in rows:
                name  = re.sub(r'\s+', '', name)
                title = re.sub(r'<[^>]+>', '', title).strip()
                # doc_id：日付＋コード＋タイトル先頭で一意化
                doc_id = f"{day}_{code}_{title[:20]}"
                results.append({
                    "id": doc_id, "code": code, "name": name,
                    "title": title, "time": day,
                })
        except Exception as e:
            print(f"公式ページ{page}エラー：{e}")
            break
    print(f"TDnet公式：{len(results)}件取得")
    return results

def fetch_yanoshin(limit=300):
    """yanoshin API（予備系統・タイムアウト頻発のため降格）"""
    url = f"https://webapi.yanoshin.jp/webapi/tdnet/list/recent.json?limit={limit}"
    for i in range(2):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            items = r.json().get("items", [])
            print(f"yanoshin API：{len(items)}件取得")
            results = []
            for it in items:
                td = it.get("Tdnet", {})
                results.append({
                    "id":    td.get("id", ""),
                    "code":  td.get("company_code", "")[:4],
                    "name":  td.get("company_name", ""),
                    "title": td.get("title", ""),
                    "time":  td.get("pubdate", ""),
                })
            return results
        except Exception as e:
            print(f"yanoshin試行{i+1}失敗：{e}")
    return []

def fetch_tdnet():
    """公式優先→yanoshinフォールバック"""
    items = fetch_tdnet_official()
    if not items:
        print("→ yanoshin APIにフォールバック")
        items = fetch_yanoshin()
    return items

# ============================================================
# スコアリング
# ============================================================
def score_disclosure(title):
    for ng in EXCLUDE_KEYWORDS:
        if ng in title:
            return 0, None
    best, hit = 0, None
    for word, sc in KEYWORD_SCORES.items():
        if word in title and sc > best:
            best, hit = sc, word
    return best, hit

# ============================================================
# メイン
# ============================================================
def main():
    now = datetime.now(JST)
    print(f"TDnetスキャン開始：{now.strftime('%Y-%m-%d %H:%M')} JST")

    seen = load_seen()
    items = fetch_tdnet()
    if not items:
        print("開示データなし・終了")
        return

    new_candidates = []
    for item in items:
        doc_id = item["id"]
        title  = item["title"]
        code   = item["code"]
        name   = item["name"]
        pub    = item["time"]

        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)

        score, word = score_disclosure(title)
        if score >= 3:  # 通知は3点以上のみ
            is_core = code in CORE_CODES
            new_candidates.append({
                "score": score + (1 if is_core else 0),
                "word": word, "code": code, "name": name,
                "title": title, "time": pub, "core": is_core,
            })

    save_seen(seen)

    if not new_candidates:
        print("新規材料なし・通知スキップ")
        return

    new_candidates.sort(key=lambda x: x["score"], reverse=True)
    fire   = [c for c in new_candidates if c["score"] >= 5]
    normal = [c for c in new_candidates if c["score"] < 5]

    lines = [f"📡 TDnet材料速報 [{now.strftime('%m/%d %H:%M')}]"]
    if fire:
        lines.append("")
        lines.append(f"🔥 最優先 {len(fire)}件")
        for c in fire[:8]:
            mark = "★コア" if c["core"] else ""
            lines.append(f"{c['code']} {c['name']} {mark}")
            lines.append(f"  [{c['score']}点/{c['word']}]")
            lines.append(f"  {c['title'][:45]}")
    if normal:
        lines.append("")
        lines.append(f"○ 通常候補 {len(normal)}件")
        for c in normal[:6]:
            mark = "★" if c["core"] else ""
            lines.append(f"{c['code']} {c['name']}{mark} [{c['word']}]")

    lines.append("")
    lines.append("→翌営業日の寄り前に出来高・気配を確認")
    lines.append("→ルール：材料当日/翌朝エントリーのみ・3日保有")

    message = "\n".join(lines)
    send_line(message)
    print(f"通知完了：🔥{len(fire)}件・○{len(normal)}件")

if __name__ == "__main__":
    main()
