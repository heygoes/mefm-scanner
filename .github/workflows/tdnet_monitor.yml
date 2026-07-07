# .github/workflows/tdnet_monitor.yml
# TDnet適時開示監視：夜間20:30 JST・朝07:40 JST に実行
name: tdnet-monitor

on:
  schedule:
    # UTC表記（JST-9時間）
    - cron: '30 11 * * 1-5'   # 20:30 JST 平日（引け後開示）
    - cron: '40 22 * * 0-4'   # 07:40 JST 平日（夜間・早朝開示）
  workflow_dispatch:          # 手動実行も可能

permissions:
  contents: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Run TDnet monitor
        env:
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
        run: python tdnet_monitor.py

      - name: Commit seen file
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add tdnet_seen.json || true
          git diff --staged --quiet || git commit -m "update tdnet_seen"
          git push || true
