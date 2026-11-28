#!/usr/bin/env python3
"""每週檢查各實體自上次資料截止日（meta.asOf）後的新交易與公告，寫成 pending.json（待人工確認），
再重建 Dashboard。不會自動改 data.json：新資訊一律要人工查證後才併入。

目錄結構（repo 根目錄）：
  template.html、build.py           ← 從 skill 取出
  data/<slug>/data.json             ← 各實體資料
  docs/<Slug>_Ecosystem_Capital_Map.html  ← 輸出（GitHub Pages）
環境變數：ANTHROPIC_API_KEY（必填）、ANTHROPIC_MODEL（預設 claude-sonnet-5-5）、MAX_ITEMS（預設 8）
"""
import json, os, re, subprocess, sys, time, urllib.error, urllib.request

API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "8"))

def ask(entity, ticker, since, known):
    prompt = f"""請用網路搜尋，找出「{entity}（{ticker}）」在 {since} 之後新公布的：投資、入股、收購、處分、合資、大型採購或算力合約、融資發債，以及財報、監管裁定等重大公告。
已收錄的交易對象（若只是既有交易的進展，也要列出並在 t 開頭標「更新：」）：{', '.join(known[:60])}
只回傳 JSON 陣列，不要其他文字。每筆格式：{{"d":"YYYY-MM-DD","t":"一句標題","x":"一句說明（含金額）","url":"原始來源網址","counterparty":"對象名稱或空字串"}}。
沒有就回傳 []。最多 {MAX_ITEMS} 筆，日期必須晚於 {since}，網址必須是你實際搜尋到的頁面。"""
    body = {"model": MODEL, "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    res = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r: res = json.load(r)
            break
        except urllib.error.HTTPError as e:
            # 把 API 回的錯誤內容讀出來：只看「400 Bad Request」無從判斷是餘額不足、模型名稱錯，還是請求格式有問題
            raw = e.read().decode("utf-8", "replace")
            try: msg = json.loads(raw).get("error", {}).get("message", "") or raw
            except Exception: msg = raw
            msg = " ".join(msg.split())[:300]
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < 2:
                wait = int(e.headers.get("retry-after") or 0) or 20 * (attempt + 1)
                print(f"   …{entity}：HTTP {e.code}，{min(wait, 90)} 秒後重試（{msg[:120]}）"); time.sleep(min(wait, 90)); continue
            raise RuntimeError(f"HTTP {e.code}：{msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2: print(f"   …{entity}：連線問題，20 秒後重試（{e}）"); time.sleep(20); continue
            raise
    text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
    m = re.search(r"\[.*\]", text, re.S)
    try: items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError: items = []
    return [i for i in items if isinstance(i, dict) and str(i.get("d", "")) > since and str(i.get("url", "")).startswith("http")]

def main(root="."):
    summary = []; failed = []; stop = ""
    has_key = bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip())
    if not has_key: print("ℹ️ 未設定 ANTHROPIC_API_KEY：略過新動態檢查，只重建各家 Dashboard（讓更新後的現值與市值反映到頁面）")
    for slug in sorted(os.listdir(os.path.join(root, "data"))):
        p = os.path.join(root, "data", slug, "data.json")
        if not os.path.exists(p): continue
        d = json.load(open(p, encoding="utf-8")); M = d["meta"]
        known = [n["name"] for n in d["nodes"]]
        seen = {e.get("t") for e in d.get("events", [])}
        items = []
        if has_key and stop:
            failed.append((M["entity"], "未查詢（" + stop + "）"))
        elif has_key:
            try: items = [i for i in ask(M["entity"], M.get("ticker", ""), M["asOf"], known) if i.get("t") not in seen]
            except Exception as e:
                print(f"⚠️ {slug}：查詢失敗 {e}（仍會重建頁面）"); failed.append((M["entity"], str(e)))
                low = str(e).lower()
                # 餘額不足、金鑰無效這類問題，後面每一家都會失敗：不再逐家重試，直接講清楚
                if "credit balance" in low or "billing" in low: stop = "API 帳戶餘額不足"
                elif "401" in low or "authentication" in low or "invalid x-api-key" in low: stop = "API 金鑰無效或已過期"
                if stop: print(f"⛔ {stop}：其餘公司這次不再查詢，只重建頁面")
        pend_p = os.path.join(root, "data", slug, "pending.json")
        old = json.load(open(pend_p, encoding="utf-8")) if os.path.exists(pend_p) else []
        urls = {o.get("url") for o in old}
        merged = old + [i for i in items if i.get("url") not in urls]
        if merged != old: json.dump(merged, open(pend_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out = os.path.join(root, "docs", f"{M.get('fileSlug', slug)}_Ecosystem_Capital_Map.html")
        subprocess.run([sys.executable, os.path.join(root, "build.py"), p, os.path.join(root, "template.html"), out], check=True)
        new = len(merged) - len(old)
        summary.append(f"| {M['entity']} | {new} | {len(merged)} |")
        if has_key and not (failed and failed[-1][0] == M["entity"]): print(f"✅ {M['entity']}：新增待確認 {new} 筆（累計 {len(merged)}）")
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as f:
            f.write("## 投資生態圈每週檢查\n\n| 實體 | 本週新增待確認 | 累計待確認 |\n|---|---|---|\n" + "\n".join(summary) + "\n")
            if failed:
                f.write(f"\n### ⚠️ 這次沒查到新動態的公司：{len(failed)} 家\n\n" + (f"**原因：{stop}。** 請到 Claude Console 處理後，再手動執行一次。\n\n" if stop else "") + "| 實體 | 原因 |\n|---|---|\n" + "\n".join(f"| {a} | {b.replace('|', '/')} |" for a, b in failed) + "\n")
    if failed:
        print(f"\n⚠️ 共 {len(failed)} 家這次沒查到新動態：" + "、".join(a for a, _ in failed) + (f"（{stop}）" if stop else ""))
        # 讓 GitHub 在執行紀錄頁顯示黃色警告，不必點進紀錄才知道
        print(f"::warning title=新動態檢查不完整::{len(failed)} 家沒有查到：" + "、".join(a for a, _ in failed) + (f"。原因：{stop}" if stop else ""))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
