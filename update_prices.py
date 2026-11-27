#!/usr/bin/env python3
"""上市持股現值自動更新：對每個有 shares（股數）與 pxTk（報價代號）的節點，抓最新收盤價重算 val。
  val（US$ 十億）＝ shares × 收盤價 × pxMult（預設 1；ADR 換股比例等）× 匯率（非美元報價自動換算）÷ 1e9
只改 val、valDate、valNote、valSrc 與自動來源 px_auto_<代號>；不動 verified（那是「人工查證日」）。
另外更新各家的市值（頂層 mkt，有 pxTk 才處理）：以人工查證的市值為基準，乘上「基準日至今的股價（與匯率）變動」。
  mkt.cap ＝ capRef × （最新收盤價 × 匯率）÷（基準日收盤價 × 基準日匯率）；第一次執行時記下 capRef、pxRef、fxRef、refDate。
  這個算法不反映股數變動（庫藏股、增資），所以每隔一段時間要重新人工查證一次市值，並刪掉 capRef 讓它重設基準。
用法：python3 update_prices.py <repo根目錄>                 ← 線上抓價（Yahoo Finance，失敗改用 Stooq）
      python3 update_prices.py <repo根目錄> --prices p.json  ← 離線：p.json = {"INTC":{"price":54.67,"date":"2026-11-18","currency":"USD","url":"…","label":"…"}}
pxTk 用 Yahoo 代號：美股 INTC、台股 3661.TW、港股 0700.HK、滬 603993.SS、深 300750.SZ、東京 9984.T。
"""
import json, os, sys, time, urllib.request, datetime
UA = {"User-Agent": "Mozilla/5.0 (ecomap price updater)"}
def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r: return r.read().decode("utf-8", "replace")
def yahoo(sym):
    j = json.loads(_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=3mo&interval=1d"))
    m = j["chart"]["result"][0]["meta"]
    d = datetime.datetime.utcfromtimestamp(m["regularMarketTime"]).strftime("%Y-%m-%d")
    hist = {}
    try:
        for ts, c in zip(j["chart"]["result"][0].get("timestamp") or [], j["chart"]["result"][0]["indicators"]["quote"][0].get("close") or []):
            if c is not None: hist[datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")] = float(c)
    except Exception: pass
    return {"price": float(m["regularMarketPrice"]), "date": d, "currency": m.get("currency", "USD"), "hist": hist,
            "url": f"https://finance.yahoo.com/quote/{sym}", "label": f"Yahoo Finance｜{sym} {d} 收盤 {m['regularMarketPrice']}"}
def stooq(sym):
    if "." in sym: raise ValueError("Stooq 備援只支援美股代號")
    row = _get(f"https://stooq.com/q/l/?s={sym.lower()}.us&f=sd2t2ohlcv&h&e=csv").strip().splitlines()[1].split(",")
    return {"price": float(row[6]), "date": row[1], "currency": "USD", "url": f"https://stooq.com/q/?s={sym.lower()}.us",
            "label": f"Stooq｜{sym} {row[1]} 收盤 {row[6]}"}
def quote(sym, cache, offline):
    if sym in cache: return cache[sym]
    if offline is not None:
        cache[sym] = offline.get(sym); return cache[sym]
    q = None
    for fn in (yahoo, stooq):
        try: q = fn(sym); break
        except Exception as e: print(f"   … {fn.__name__} {sym} 失敗：{e}")
    cache[sym] = q; time.sleep(0.4); return q
def fx_to_usd(cur, cache, offline):
    if cur in ("USD", None, ""): return 1.0
    if cur == "GBp": return (fx_to_usd("GBP", cache, offline) or 0) / 100
    q = quote(f"{cur}USD=X", cache, offline)
    return q["price"] if q else None
def close_on(q, day):
    """基準日（或之前最近一個交易日）的收盤價；沒有歷史資料時回傳 None。"""
    ds = sorted(k for k in (q.get("hist") or {}) if k <= str(day))
    return q["hist"][ds[-1]] if ds else None
def fx_on(cur, day, cache, offline):
    if cur in ("USD", None, ""): return 1.0
    q = quote(f"{cur}USD=X", cache, offline)
    return (close_on(q, day) if q else None)
def fmt(v): return f"${v*10:,.1f} 億" if v < 1 else f"${v*10:,.0f} 億"
def main():
    a = sys.argv[1:]; offline = None
    if "--prices" in a:
        i = a.index("--prices"); offline = json.load(open(a[i+1], encoding="utf-8")); del a[i:i+2]
    root = a[0] if a else "."; cache = {}; rows = []; fail = []; caps = []
    base = os.path.join(root, "data") if os.path.isdir(os.path.join(root, "data")) else root
    for slug in sorted(os.listdir(base)):
        p = os.path.join(base, slug, "data.json")
        if not os.path.exists(p): continue
        d = json.load(open(p, encoding="utf-8")); changed = False
        for n in d["nodes"]:
            sh, sym = n.get("shares"), n.get("pxTk")
            if not sh or not sym: continue
            q = quote(sym, cache, offline)
            if not q: fail.append(f"{slug}/{n['id']}（{sym}）"); continue
            fx = fx_to_usd(q.get("currency"), cache, offline)
            if fx is None: fail.append(f"{slug}/{n['id']}（{q.get('currency')} 匯率）"); continue
            mult = n.get("pxMult", 1)
            val = round(sh * q["price"] * mult * fx / 1e9, 4)
            if n.get("valDate") and str(n["valDate"]) > q["date"]: continue     # 手上已有更新的估值，不倒退
            key = "px_auto_" + "".join(c if c.isalnum() else "_" for c in sym)
            d["sources"][key] = [q.get("label") or f"{sym} {q['date']} 收盤 {q['price']}", q["url"], "B"]
            keep = [k for k in n.get("valSrc", []) if not k.startswith("px_")]      # 保留股數出處，換掉舊的價格來源
            old = n.get("val")
            hand = (n.get("pxNote") or "").strip()
            n.update(val=val, valDate=q["date"], valSrc=[key] + keep,
                     valNote=f"{sh:,.0f} 股 × {q['date']} 收盤 {q['price']:,.2f} {q.get('currency','USD')}" + (f" × {mult:g}" if mult != 1 else "") +
                             (f" × 匯率 {fx:.5f}" if fx != 1 else "") + f" ≈ {fmt(val)}（自動計算）" + (f"；{hand}" if hand else ""))
            changed = True; rows.append((d["meta"]["entity"], n["name"], sym, old, val, q["date"]))
        mk = d.get("mkt")
        if isinstance(mk, dict) and mk.get("pxTk") and isinstance(mk.get("cap"), (int, float)):
            sym = mk["pxTk"]; q = quote(sym, cache, offline)
            fx = fx_to_usd(q.get("currency"), cache, offline) if q else None
            if not q or fx is None: fail.append(f"{slug}/市值（{sym}）")
            else:
                if "capRef" not in mk:      # 第一次：以人工查證的市值與其日期為基準
                    px0 = close_on(q, mk.get("date", "")); fx0 = fx_on(q.get("currency"), mk.get("date", ""), cache, offline)
                    exact = px0 is not None and fx0 is not None
                    mk.update(capRef=mk["cap"], pxRef=px0 if exact else q["price"], fxRef=fx0 if exact else fx,
                              refDate=str(mk.get("date", "")) if exact else q["date"], refExact=exact)
                if q["date"] >= str(mk.get("refDate", "")):
                    old = mk["cap"]; cap = round(mk["capRef"] * (q["price"] * fx) / (mk["pxRef"] * mk["fxRef"]), 1)
                    key = "px_auto_" + "".join(c if c.isalnum() else "_" for c in sym)
                    d["sources"][key] = [q.get("label") or f"{sym} {q['date']} 收盤 {q['price']}", q["url"], "B"]
                    mk["src"] = [k for k in mk.get("src", []) if not k.startswith("px_")] + [key]
                    mk.update(cap=cap, date=q["date"],
                              note=f"以 {mk['refDate']} 的市值 {fmt(mk['capRef'])} × 股價" + ("與匯率" if fx != 1 else "") + "變動推算（自動，不反映股數變動）" +
                                   ("" if mk.get("refExact") else "；基準價取自首次自動更新當日") + (f"；{mk['hand']}" if mk.get("hand") else ""))
                    changed = True; caps.append((d["meta"]["entity"], sym, old, cap, q["date"]))
        if changed: json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows: print(f"✅ {r[0]}｜{r[1]}（{r[2]}）：{'—' if r[3] is None else fmt(r[3])} → {fmt(r[4])}（{r[5]}）")
    for r in caps: print(f"💰 {r[0]} 市值（{r[1]}）：{fmt(r[2])} → {fmt(r[3])}（{r[4]}）")
    if fail: print("⚠️ 取不到報價（現值維持原樣）：" + "、".join(fail))
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as f:
            f.write("## 上市持股現值更新\n\n| 實體 | 持股 | 代號 | 原現值 | 新現值 | 報價日 |\n|---|---|---|---|---|---|\n" +
                    "\n".join(f"| {r[0]} | {r[1]} | {r[2]} | {'—' if r[3] is None else fmt(r[3])} | {fmt(r[4])} | {r[5]} |" for r in rows) +
                    "\n\n## 市值更新\n\n| 公司 | 代號 | 原市值 | 新市值 | 報價日 |\n|---|---|---|---|---|\n" +
                    "\n".join(f"| {r[0]} | {r[1]} | {fmt(r[2])} | {fmt(r[3])} | {r[4]} |" for r in caps) +
                    ("\n\n取不到報價：" + "、".join(fail) if fail else "") + "\n")
    print(f"共更新 {len(rows)} 個節點、{len(caps)} 家市值、{len(fail)} 個失敗")
if __name__ == "__main__": main()
