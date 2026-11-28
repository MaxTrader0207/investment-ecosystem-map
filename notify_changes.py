#!/usr/bin/env python3
"""每週更新後，若有公司燈號變動，就開一個 GitHub Issue 通知（repo 擁有者預設會收到 email）。
用法：python notify_changes.py [repo 根目錄]   需要環境變數 GH_TOKEN（GitHub Actions 內建的 GITHUB_TOKEN 即可）。
同一期、同一批變動只會開一次。"""
import json, os, subprocess, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."
log = json.load(open(os.path.join(root, "data", "changelog.json"), encoding="utf-8")).get("log", [])
if not log:
    sys.exit(0)
e = log[0]
lights = [x for x in e.get("auto", []) if x.get("t") == "燈號變動"]
if not lights:
    print("沒有燈號變動，不通知"); sys.exit(0)
names = "、".join(x["e"] for x in lights[:4]) + ("…" if len(lights) > 4 else "")
title = f"燈號變動 {e['d']}：{names}（共 {len(lights)} 家）"
body = "\n".join([f"資料日期 **{e['d']}**（上一期 {e.get('from', '—')}），以下公司的風險燈號有變動：", ""]
                 + [f"- **{x['e']}**：{x.get('x', '')}（{x.get('why', '')}）" for x in lights]
                 + ["", "完整內容：https://maxtrader0207.github.io/investment-ecosystem-map/Ecosystem_Network_Map.html#s-chg", "",
                    "_此為資訊整理，非投資建議。這則通知由每週更新流程自動產生。_"])
try:
    have = subprocess.run(["gh", "issue", "list", "--state", "all", "--search", f'"{title}" in:title', "--json", "title"],
                          capture_output=True, text=True, check=True).stdout
    if any(i.get("title") == title for i in json.loads(have or "[]")):
        print("這一批變動已經通知過"); sys.exit(0)
    subprocess.run(["gh", "issue", "create", "--title", title, "--body", body], check=True)
    print("已開 Issue：", title)
except Exception as ex:   # 通知失敗不該讓整個更新流程失敗
    print("⚠️ 通知未送出：", ex)
