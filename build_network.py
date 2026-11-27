#!/usr/bin/env python3
"""跨實體總網路圖建置器：彙整多份 data.json，合併同名交易對手，輸出單檔互動 HTML（含樞紐排行、「若出事」曝險、多實體比較）。
用法：python3 build_network.py network_template.html Ecosystem_Network_Map.html a/data.json b/data.json ...（可用萬用字元）
各實體 Dashboard 須與輸出檔放在同一資料夾，檔名為 <fileSlug>_Ecosystem_Capital_Map.html，連結才會通。
節點可設 "netSkip": true 排除（例如自身 IPO、回購、資本支出這類非交易對手節點）。"""
import json,re,glob,os,sys
ALIAS=[("NVIDIA",r"nvidia|輝達"),("AMD",r"^amd\b|^amd（|超微"),("Google／Alphabet",r"google|alphabet|谷歌"),("Meta",r"^meta\b|meta platforms"),
("Microsoft",r"microsoft|微軟"),("Amazon",r"amazon|aws"),("Oracle",r"oracle"),("TSMC 台積電",r"台積電|tsmc"),("Intel",r"^intel|英特爾"),
("Broadcom",r"broadcom|博通"),("Anthropic",r"anthropic"),("OpenAI",r"openai"),("SpaceX",r"spacex"),("xAI",r"^xai"),("DeepSeek",r"deepseek|深度求索"),
("騰訊 Tencent",r"騰訊|tencent"),("阿里巴巴 Alibaba",r"阿里巴巴|alibaba"),("Apple",r"^apple"),("Arm",r"^arm\b|^arm（|arm holdings"),("Blue Owl",r"blue owl"),
("BlackRock",r"blackrock"),("Apollo",r"apollo"),("Silver Lake",r"silver lake"),("SoftBank",r"softbank|軟銀"),("Samsung",r"samsung|三星"),("Qualcomm",r"qualcomm|高通"),
("Huawei",r"huawei|華為"),("CoreWeave",r"coreweave"),("Nebius",r"nebius"),("Ayar Labs",r"ayar"),("Cerebras",r"cerebras"),("Crusoe",r"crusoe"),("Fluidstack",r"fluidstack"),
("Mobileye",r"mobileye"),("Terafab",r"terafab"),("Tesla",r"^tesla"),("Stellantis",r"stellantis"),("Ford",r"^ford"),("Scale AI",r"scale ai"),("EssilorLuxottica",r"essilor"),
("字節跳動 ByteDance",r"字節|bytedance"),("寧德時代 CATL",r"寧德|catl"),("聯發科 MediaTek",r"聯發科|mediatek"),("宇樹 Unitree",r"宇樹|unitree"),("美團 Meituan",r"美團|meituan"),("紅杉 Sequoia",r"紅杉|sequoia"),("HUMAIN",r"humain"),("MGX",r"mgx"),("Valor",r"valor"),("Cursor",r"cursor"),("Vistra",r"vistra"),("SK hynix",r"hynix"),("PIF",r"\bpif\b|public investment fund|公共投資基金")]
def canon(name,tk="",skip=None):
    s=name.strip(); low=s.lower()
    for lab,rx in ALIAS:
        if lab==skip: continue      # 節點名稱帶到自家別名（例如 Amazon 檔的「OpenAI（AWS 客戶）」）時，不可歸到自己
        if re.search(rx,low) or (tk and re.search(rx,tk.lower())): return lab
    base=re.sub(r"[（(].*?[)）]","",s).strip()
    return base or s
def grade(t,u):
    t=str(t);u=str(u).lower()
    if re.search(r"洽談|傳出|據傳|傳聞|消息人士|知情人士|reportedly|in talks|rumou?r|weighs|considers|擬參與",t,re.I): return "D"
    if re.search(r"sec\.gov|hkexnews|\.gov\b|\.gov\.|newsroom|investor\.|//ir\.|about\.fb\.com|nvidianews|businesswire|prnewswire|globenewswire|mops\.twse|cninfo|szse\.cn|sse\.com|dfcfw\.com/pdf|intc\.com|media\.stellantis|pr\.tsmc|media-room",u): return "A"
    if re.search(r"caifuhao|hao\.cnyes|blog|medium\.com|substack|reddit|stocktwits|etoro|sacra\.com|dev\.to|towardsai|wikipedia|fourweekmba|fool\.com|247wallst|tradingview|uanalyze|stockfeel|statementdog|line\.me",u): return "C"
    if re.search(r"reuters|bloomberg|wsj\.com|ft\.com|cnbc|caixinglobal|nikkei|cna\.com\.tw|udn\.com|ctee\.com|technews|economist|theinformation|techcrunch|scmp\.com|aljazeera|fortune\.com|digitimes|trendforce|jiemian|cls\.cn|wallstreetcn|yicai|stheadline|apnews|anuenews|theregister|tomshardware|datacenterdynamics|36kr\.com|chinatimes|ltn\.com|barrons|axios|nytimes|washingtonpost|theverge|wired|businessinsider|insidermonkey|seekingalpha|thenextweb|siliconangle|finance\.yahoo|aol\.com|marketwatch|techrepublic|electrive|engadget|nownews|ifeng|sina\.c|eastmoney|mining\.com|world-nuclear-news|ans\.org|verdict\.co|energytrend|businesstoday|business-standard|livemint|heise\.de|calcalistech|timesofisrael|ynetnews",u) or re.search(r"Reuters|Bloomberg|路透|彭博|AP（|WSJ",t): return "B"
    if re.search(r"新聞稿|Newsroom|官方公告|重大訊息|10-Q|8-K|10-K|20-F|press release|Reports (First|Second|Third|Fourth)",t,re.I): return "A"
    return "C"
def fmtb(v): return ("$%s億"%format(round(v*10),",")) if v>=1 else ("$%.1f億"%(v*10))
AMT={"equity":"股權成本","capex":"自建投資","commitment":"承諾上限","contract":"合約價值","project":"專案總額","inflow":"流入資金","disposal":"處分回收","return":"股東回饋","liability":"會計負債","none":"未揭露"}
ents=[];links=[];allpairs=set()
if len(sys.argv)<4: sys.exit(__doc__)
TPL,OUT=sys.argv[1],sys.argv[2]
FILES=sorted({p for a in sys.argv[3:] for p in glob.glob(a)})
SKIP_IDS={"dod","usreg","hungov","ndrc","fab28","escrow","govt","capex","buyback","ipo","bond","bonds","offer","hipo","hplace","classc","seriesg","seriesh","founder","founders","musk","zeng","capacity"}
for fp in FILES:
    D=json.load(open(fp,encoding="utf-8")); M=D["meta"]; S=D["sources"]
    cats={c["id"]:c for c in D["categories"]}
    f=f"{M.get('fileSlug') or M['entity']}_Ecosystem_Capital_Map.html"
    ek=canon(M["entity"],M.get("ticker",""))
    st={"tot":{},"grade":{"A":0,"B":0,"C":0,"D":0},"stale":0,"rumor":0,"risk":{},"cpNodes":0,"loops":len(D.get("loops",[])),
        "loopsQ":sum(1 for l in D.get("loops",[]) if l.get("back") is not None),"val":0,"events":len(D.get("events",[])),"top":[],"skip":{}}
    for n in D["nodes"]:
        c=cats.get(n["cat"],{})
        if c.get("counterparty"): st["cpNodes"]+=1; continue
        gs=[grade(S[s][0],S[s][1]) if len(S[s])<3 else S[s][2] for s in n["src"] if s in S]; g=sorted(gs)[0] if gs else "D"
        st["grade"][g]+=1
        if n.get("verified",M["asOf"]) is None: st["stale"]+=1
        if n.get("unconfirmed") or g=="D": st["rumor"]+=1
        for r in n.get("risks",[]): st["risk"][r["k"]]=st["risk"].get(r["k"],0)+1
        if n.get("val") is not None: st["val"]+=1
        t=n.get("amtType","equity")
        if n.get("amt") is not None and not n.get("excludeFromSum") and not n.get("per"):
            st["tot"][t]=round(st["tot"].get(t,0)+n["amt"],3)
        elif t!="none":      # 有這類節點但沒進加總：分成「金額未揭露」「年度金額」「避免重複而排除」
            k="und" if n.get("amt") is None else ("per" if n.get("per") else "excl")
            st["skip"].setdefault(t,{"und":0,"per":0,"excl":0})[k]+=1
    st["top"]=[[n["name"],n.get("short",""),AMT.get(n.get("amtType","none"),"")] for n in sorted([n for n in D["nodes"] if n.get("amt") is not None and not cats.get(n["cat"],{}).get("counterparty") and not n.get("excludeFromSum")],key=lambda n:-n["amt"])[:3]]
    ents.append({"key":ek,"entity":M["entity"],"ticker":M.get("ticker",""),"accent":M.get("accent","#888"),"file":f,"asOf":M["asOf"],"nodes":len(D["nodes"]),"st":st,"sub":M.get("subtitle",""),"thesis":(D.get("ic") or {}).get("thesis","") if isinstance(D.get("ic"),dict) else "",
        "fin":(dict(D["fin"],src=[[S[x][0],S[x][1]] for x in D["fin"].get("src",[]) if x in S]) if isinstance(D.get("fin"),dict) else None),
        "rk":{"n":sum(1 for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty")),
              "eq":[n["amt"] for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and n.get("amtType","equity")=="equity" and n.get("direction","out")!="in" and n.get("amt") is not None and not n.get("excludeFromSum") and not n.get("per")],
              "dep":[l.get("dep") for l in D.get("loops",[]) if l.get("dep")],
              "guar":sum(1 for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and (n.get("guarantee") or "擔保" in n.get("type","") or n.get("amtType")=="liability" or any(r["k"]=="fin" for r in n.get("risks",[])))),
              "unc":sum(1 for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and (n.get("unconfirmed") or any(r["k"]=="exec" for r in n.get("risks",[])))),
              "gamt":sum((n.get("guarAmt") if n.get("guarAmt") is not None else (n.get("amt") or 0)) for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and not n.get("excludeFromSum")
                         and (n.get("guarAmt") is not None or n.get("amtType")=="liability" or ("擔保" in n.get("type","") and n.get("amtType") in ("commitment","none")))),
              "macro":{mk:dict(mv,src=[[S[x][0],S[x][1]] for x in mv.get("src",[]) if x in S]) for mk,mv in (D.get("macro") or {}).items() if isinstance(mv,dict)}}})
    for n in D["nodes"]:
        if n["cat"] not in cats: continue
        c=cats[n["cat"]]
        k=canon(n["name"],n.get("tk",""))
        if k==ek: k=canon(n["name"],n.get("tk",""),skip=ek)
        allpairs.add((ek,k))
        if n.get("netSkip") or n["id"] in SKIP_IDS: continue
        gs=[grade(S[s][0],S[s][1]) if len(S[s])<3 else S[s][2] for s in n["src"] if s in S]
        g=sorted(gs)[0] if gs else "D"
        links.append({"ent":ek,"cp":k,"name":n["name"],"cat":c["name"],"counterparty":bool(c.get("counterparty")),"type":n.get("type",""),
          "amtType":n.get("amtType","none"),"dir":n.get("direction","out"),"amt":n.get("amt"),"short":n.get("short",""),"date":n.get("date",""),
          "status":n.get("status",""),"grade":g,"rumor":bool(n.get("unconfirmed")) or g=="D","excl":bool(n.get("excludeFromSum") or n.get("per")),"risks":[r["k"] for r in n.get("risks",[])],
          "src":[[S[s][0],S[s][1]] for s in n["src"] if s in S][:3],
          "val":n.get("val"),"valDate":n.get("valDate",""),"xnote":n.get("xnote",""),"per":n.get("per",""),"term":n.get("term"),"annual":n.get("annual")})
entkeys={e["key"] for e in ents}
from collections import defaultdict
by=defaultdict(list)
for l in links: by[l["cp"]].append(l)
hubs=[]
for k,ls in by.items():
    es=sorted(set(l["ent"] for l in ls)|({k} if k in entkeys else set()))
    tot=defaultdict(float)
    for l in ls:
        if l["amt"] is not None and not l["excl"]: tot[l["amtType"]]+=l["amt"]
    hubs.append({"key":k,"isEntity":k in entkeys,"ents":es,"deg":len(es),"links":len(ls),"tot":tot})
for e in ents: e["st"]["hubs"]=sum(1 for h in hubs if h["deg"]>=2 and e["key"] in h["ents"] and h["key"]!=e["key"])
# ---- 跨實體一致性檢查：同一筆關係在不同實體檔的金額是否對得上 ----
def near(a,b,tol=0.15): return a is not None and b is not None and abs(a-b)<=tol*max(abs(a),abs(b),1e-9)
def item(l): return {"ent":l["ent"],"name":l["name"],"short":l["short"],"amt":l["amt"],"amtType":l["amtType"],"dir":l["dir"],"date":l["date"],"val":l["val"],"valDate":l["valDate"],"xnote":l["xnote"],"rumor":l["rumor"]}
checks=[]
real=[l for l in links if l["amt"] is not None and not l["per"]]
# (a) 雙向：A 檔記「對 B」、B 檔記「對 A」
seen=set()
for a in real:
    if a["cp"] not in entkeys or a["cp"]==a["ent"]: continue
    for b in real:
        if b["ent"]!=a["cp"] or b["cp"]!=a["ent"] or a["dir"]==b["dir"]: continue
        ta,tb=a["amtType"],b["amtType"]
        inv=lambda x,y: x in ("equity","commitment") and y in ("inflow","commitment")      # 投資方 ↔ 被投資方
        buy=lambda x,y: x in ("commitment","contract") and y=="contract"                    # 買方 ↔ 賣方
        if not (inv(ta,tb) or inv(tb,ta) or buy(ta,tb) or buy(tb,ta)): continue
        key=tuple(sorted([a["ent"]+"|"+a["name"],b["ent"]+"|"+b["name"]]))
        if key in seen: continue
        seen.add(key)
        ok=near(a["amt"],b["amt"]) or near(a.get("val"),b["amt"]) or near(a["amt"],b.get("val"))
        for cap,act in ((a,b),(b,a)):   # 一方是承諾上限、另一方是已到位金額：不超過上限即一致
            if cap["amtType"]=="commitment" and act["amtType"] in ("inflow","equity") and act["amt"]<=cap["amt"]*1.15: ok=True
        flags=[]
        if a["rumor"]!=b["rumor"]: flags.append("一方標為傳聞／未定案，另一方沒有"); ok=False
        ya,yb=re.match(r"(\d{4})(?:-(\d{2}))?",a["date"] or ""),re.match(r"(\d{4})(?:-(\d{2}))?",b["date"] or "")
        if ya and yb and abs((int(ya[1])-int(yb[1]))*12+int(ya[2] or 6)-int(yb[2] or 6))>12: flags.append("兩邊記載的日期相差超過一年，請確認是否為同一事件")
        checks.append({"kind":"雙向","cp":a["ent"]+" ↔ "+b["ent"],"ok":ok,"items":[item(a),item(b)],"flags":flags})
# (a2) 單邊記載：A 檔有記對 B 的金額關係，但 B 檔完全沒有 A 這個節點
MONEY=("equity","commitment","contract","inflow","project")
one=set()
for a in real:
    if a["cp"] in entkeys and a["cp"]!=a["ent"] and a["amtType"] in MONEY and (a["cp"],a["ent"]) not in allpairs and not a["counterparty"]:
        key=(a["ent"],a["cp"])
        if key in one: continue
        one.add(key)
        checks.append({"kind":"單邊記載","cp":a["ent"]+" → "+a["cp"],"ok":False,"single":True,"items":[item(a),{"ent":a["cp"],"name":"（沒有對應節點）","short":"—","amt":None,"amtType":"none","dir":"","date":"","val":None,"valDate":"","xnote":"","rumor":False}]})
# (b) 同向同口徑：兩家以上都記同一個第三方、口徑相同（專案／合資／收購對象）
for k,ls in by.items():
    if k in entkeys: continue
    g=defaultdict(list)
    for l in ls:
        if l["amt"] is not None and not l["per"] and l["amtType"] in ("project","capex"): g[l["amtType"]].append(l)
    for tp,xs in g.items():
        if len({x["ent"] for x in xs})<2: continue
        am=[x["amt"] for x in xs]
        checks.append({"kind":"同一專案","cp":k,"ok":near(min(am),max(am)),"items":[item(x) for x in xs]})
    # (c) 買賣雙方：一方記股權／收購、另一方記處分
    eq=[l for l in ls if l["amt"] is not None and l["amtType"]=="equity"]; ds=[l for l in ls if l["amt"] is not None and l["amtType"]=="disposal"]
    for e in eq:
        for d_ in ds:
            if e["ent"]!=d_["ent"] and "收購" in (e["type"]+e["name"]): checks.append({"kind":"買賣雙方","cp":k,"ok":d_["amt"]<=e["amt"]*1.15,"items":[item(e),item(d_)]})
for c in checks:
    c["explained"]=any(i["xnote"] for i in c["items"]); c.setdefault("flags",[])
    c["status"]="一致" if c["ok"] else ("已說明" if c["explained"] else ("單邊" if c.get("single") else "待確認"))
checks.sort(key=lambda c:{"待確認":0,"單邊":1,"已說明":2,"一致":3}[c["status"]])
# ---- 跨實體資金閉環偵測：把所有有金額的關係接成有向圖，找出 2–4 個環節的閉環 ----
G=defaultdict(dict)
for l in links:
    und=l["amt"] is None      # 金額未揭露的供應／採購關係也納入，但每條閉環最多一段
    if und and (l["cp"] not in entkeys or re.search(r"訴訟|無金流|競爭|終止|取消",l["type"]+l["short"]+l["status"])): continue
    if not und and l["amtType"] not in MONEY+("capex",): continue
    u,v=(l["cp"],l["ent"]) if l["dir"]=="in" else (l["ent"],l["cp"])
    if u==v: continue
    e=G[u].get(v)
    if e is None or (e["amt"] is None and not und) or (not und and e["amt"] is not None and ((e["rumor"] and not l["rumor"]) or (e["rumor"]==l["rumor"] and l["amt"]>e["amt"]))):
        G[u][v]={"amt":l["amt"],"type":l["type"],"short":l["short"],"amtType":l["amtType"],"rumor":l["rumor"],"per":l["per"],"by":l["ent"],"name":l["name"]}
cycles=[]; seenc=set()
def walk(start,path):
    u=path[-1]
    for v in G.get(u,{}):
        if v==start and len(path)>=2:
            if tuple(sorted(path)) in seenc and len(path)==2: continue
            r=min(range(len(path)),key=lambda i:path[i]); canonp=tuple(path[r:]+path[:r])
            if canonp in seenc: continue
            seenc.add(canonp); seenc.add(tuple(sorted(path))) if len(path)==2 else None
            es=[dict(G[path[i]][path[(i+1)%len(path)]],**{"from":path[i],"to":path[(i+1)%len(path)]}) for i in range(len(path))]
            if sum(e["amt"] is None for e in es)>1 or sum(e["amt"] is not None for e in es)<2: continue
            mi=min((i for i in range(len(es)) if es[i]["amt"] is not None),key=lambda i:es[i]["amt"])
            cycles.append({"path":list(path),"edges":es,"min":es[mi]["amt"],"minIdx":mi,"len":len(path),"ents":sum(1 for x in path if x in entkeys),"rumor":any(e["rumor"] for e in es),"und":any(e["amt"] is None for e in es)})
        elif v not in path and len(path)<4 and v>start: walk(start,path+[v])
for s in sorted(G): walk(s,[s])
cycles.sort(key=lambda c:(c["und"],-c["min"],c["len"]))
# ---------- 風險總覽：每個實體 10 個面向（0–100）× 權重 → 總風險值與燈號 ----------
# 前 7 個面向由現有資料依固定公式換算；地緣政治、匯率、通膨／物價／利率需要 data.json 的 macro 欄位
# （macro:{"geo":{"score":0-100,"basis":"…","src":["key"]},"fx":{…},"infl":{…}}），沒有就標示待補、不計入總分。
# 權重不寫死：每次建置依全部公司的分數自動計算（等權與離散度權重各半，見下方 _weights）
RISK_DIMS=[("geo","地緣政治／出口管制"),("ceo","經營者與接班"),("inv","對外投資集中度"),("loop","循環融資依賴"),("fin","擔保與或有負債"),("conc","客戶與對手集中"),
           ("infl","通膨／物價／利率"),("reg","監管與治理"),("fx","匯率"),("exec","執行／未定案"),("info","資訊可信度")]
ALERT=85   # 單項警示門檻
def _weights(ents):
    """離散度權重（標準差法）：某面向在各公司之間的分數差異愈大（愈能區分公司），權重愈高；與等權各半混合以免極端。
    有分數的公司少於 5 家時只用等權。不用熵權法，因為它會把多數公司為 0 分的面向權重拉得過高。"""
    K=[k for k,_ in RISK_DIMS]; d={}
    for i,k in enumerate(K):
        xs=[e["risk"]["dims"][i]["s"] for e in ents if e["risk"]["dims"][i]["s"] is not None]
        if len(xs)<5: d[k]=None; continue
        m=sum(xs)/len(xs); d[k]=(sum((x-m)**2 for x in xs)/len(xs))**0.5
    ok=[v for v in d.values() if v is not None]; tot=sum(ok); eq=1/len(K)
    w={k:(0.5*eq+0.5*(d[k]/tot*len(ok)/len(K)) if d[k] is not None and tot>0 else eq) for k in K}
    z=sum(w.values()); return {k:round(v/z*100,1) for k,v in w.items()}
_INV=re.compile("股權|特別股|普通股|收購|入股|增資|參與|輪|可轉|認股|權證|認購|配售|PIPE|股東|合資|基金|LP|投資|技術授權|持股")
_NOTINV=re.compile("採購|雲端|合約|租|代工|資本支出|計畫|投資承諾|發債|公司債|回購|貸款|籌資|訴訟|競爭"); _DEAD=re.compile("撤銷|終止|取消|出清|出售")
def _cap(v): return int(round(max(0,min(100,v))))
def _flag(c,n,thr,full=5): return 0.5*min(100,c/n/thr*100)+0.5*min(100,c/full*100)   # 旗標類：占比與絕對數量各半（full＝幾個就算滿分）
for e in ents:
    rk=e.pop("rk"); st=e["st"]; n=max(rk["n"],15); k=e["key"]; R={}   # 節點少於 15 個時以 15 計，避免資料少的公司占比被放大
    # 與「投資簡覽」相同的認定：股權成本，加上屬於入股／收購／合資性質的承諾
    eq=[l["amt"] for l in links if l["ent"]==k and l["dir"]!="in" and l["amt"] is not None and not l["excl"] and not _DEAD.search(l["type"]) and (l["amtType"]=="equity" or (l["amtType"] in ("commitment","project") and _INV.search(l["type"]) and not _NOTINV.search(l["type"])))]
    tot=sum(eq)
    if eq and tot>0:
        hhi=sum((x/tot)**2 for x in eq); sc=min(1,tot/10)
        R["inv"]=(_cap(hhi*100*sc),f"共 {len(eq)} 筆股權類投資、合計 {fmtb(tot)}；最大單筆占 {max(eq)/tot*100:.0f}%（集中度 {hhi*100:.0f} × 規模係數 {sc:.2f}）")
    else: R["inv"]=(0,"沒有已揭露金額的對外股權投資")
    dv={"high":100,"mid":60,"low":20}; ds=[dv[d] for d in rk["dep"] if d in dv]
    nc=sum(1 for c in cycles if k in c["path"])
    R["loop"]=(_cap(0.7*(sum(ds)/len(ds) if ds else 0)+0.3*min(100,nc*10)),f"{len(ds)} 條資金循環的依賴程度平均（高 {rk['dep'].count('high')}、中 {rk['dep'].count('mid')}、低 {rk['dep'].count('low')}）；參與 {nc} 個跨實體閉環")
    ga=rk["gamt"]; gr=ga/(ga+tot) if ga>0 else 0
    R["fin"]=(_cap(0.6*gr*100+0.4*_flag(rk["guar"],n,0.20)),(f"擔保與負債金額 {fmtb(ga)}，相當於「擔保負債＋股權類投資」的 {gr*100:.0f}%（占六成權重）；" if ga>0 else "沒有已揭露金額的擔保或負債節點；")+f"{rk['guar']} 個節點有擔保、負債或財務風險旗標（占四成權重）")
    cl=[l for l in links if l["ent"]==k and l["amtType"] in ("contract","commitment","inflow","project") and l["amt"] is not None and not l["excl"]]
    bycp={}
    for l in cl: bycp[l["cp"]]=bycp.get(l["cp"],0)+l["amt"]
    ct=sum(bycp.values()); top=max(bycp.items(),key=lambda x:x[1]) if bycp else None
    cf=st["risk"].get("conc",0)
    R["conc"]=(_cap(0.5*_flag(cf,n,0.15,3)+0.5*(top[1]/ct*100 if top and len(bycp)>1 else (100 if top else 0))),
               (f"合約與承諾金額最大對手 {top[0]} 占 {top[1]/ct*100:.0f}%（共 {len(bycp)} 個對手）；" if top else "沒有已揭露金額的合約；")+f"{cf} 個節點有集中度旗標")
    rf=st["risk"].get("reg",0)
    R["reg"]=(_cap(_flag(rf,n,0.15)),f"{rf}／{rk['n']} 個節點有監管或治理旗標（占比達 15% 與數量達 5 個各算一半）")
    R["exec"]=(_cap(_flag(rk["unc"],n,0.25)),f"{rk['unc']}／{rk['n']} 個節點未定案或有執行風險旗標（占比達 25% 與數量達 5 個各算一半）")
    low=st["grade"]["C"]+st["grade"]["D"]+st["stale"]
    R["info"]=(_cap(_flag(low,n,0.40,8)),f"{st['grade']['C']+st['grade']['D']} 個節點來源等級為 C 或 D、{st['stale']} 個待重新查證（占比達 40% 與數量達 8 個各算一半）")
    for mk in ("geo","fx","infl","ceo"):
        m=rk["macro"].get(mk)
        if isinstance(m,dict) and isinstance(m.get("score"),(int,float)): R[mk]=(_cap(m["score"]),m.get("basis",""),m.get("src",[]))
    dims=[]
    for key,name in RISK_DIMS:
        r=R.get(key)
        dims.append({"k":key,"n":name,"w":0,"s":r[0] if r else None,"b":r[1] if r else (rk["macro"].get(key,{}).get("basis") or "待補資料：需要另外查證公開數據後才能評分"),"src":list(r[2]) if r and len(r)>2 else []})
    e["risk"]={"dims":dims}
_W=_weights(ents)
for e in ents:
    dims=e["risk"]["dims"]
    for d in dims: d["w"]=_W[d["k"]]
    cov=sum(d["w"] for d in dims if d["s"] is not None)
    e["risk"].update({"cov":int(round(cov)),"total":int(round(sum(d["s"]*d["w"] for d in dims if d["s"] is not None)/cov)) if cov else None})
    # 燈號：總分 45 以上紅、30–44 黃、29 以下綠；任一面向達 ALERT 分（單項警示）時，總燈號至少升一級，避免嚴重的單一風險被平均稀釋
    t=e["risk"]["total"]; base=0 if t is None else 3 if t>=45 else 2 if t>=30 else 1
    al=[[d["n"],d["s"]] for d in sorted(dims,key=lambda d:-(d["s"] or 0)) if d["s"] is not None and d["s"]>=ALERT and d["k"]!="info"]   # 資訊可信度反映的是資料品質，不是公司本身的風險，不觸發警示
    e["risk"].update({"base":base,"alert":al,"light":min(3,base+1) if al and base else base})
_rank=sorted([e for e in ents if e["risk"]["total"] is not None],key=lambda e:-e["risk"]["total"])
for i,e in enumerate(_rank): e["risk"]["rank"]=1+sum(1 for x in _rank if x["risk"]["total"]>e["risk"]["total"]); e["risk"]["of"]=len(_rank)
cycles=cycles[:40]
# ---------- 年化金流：有揭露年期（term）或實際年金額（annual）的合約 → 付款方→收款方的每年金額 ----------
# 用於「循環融資占營收」「每年現金缺口」「付款時程」「情境試算」。同一對付款方／收款方兩邊檔案都有時，以付款方那份為準。
_fl={}
for l in links:
    if l["amtType"] not in ("contract","commitment") or l["amt"] is None or not (l.get("term") or l.get("annual")): continue
    if _INV.search(l["type"]) and not _NOTINV.search(l["type"]): continue
    payer,payee=(l["cp"],l["ent"]) if l["dir"]=="in" else (l["ent"],l["cp"])
    t=l.get("term") or {}; tot=t.get("firm",l["amt"]); yrs=(t["e"]-t["s"]+1) if t else None
    f={"from":payer,"to":payee,"annual":round(l["annual"] if l.get("annual") else tot/yrs,2),"total":tot if t else None,"s":t.get("s"),"e":t.get("e"),"name":l["name"],"short":l["short"],"by":l["ent"],"src":l["src"][:1],"actual":bool(l.get("annual"))}
    k=(payer,payee)
    if k not in _fl or (l["ent"]==payer and _fl[k]["by"]!=payer): _fl[k]=f
flows=sorted(_fl.values(),key=lambda f:-f["annual"])
_inv={(l["ent"],l["cp"]) for l in links if l["dir"]!="in" and l["amt"] is not None and not _DEAD.search(l["type"]) and (l["amtType"]=="equity" or (l["amtType"] in ("commitment","project") and _INV.search(l["type"]) and not _NOTINV.search(l["type"])))}
_inv|={(l["cp"],l["ent"]) for l in links if l["dir"]=="in" and l["amt"] is not None and l["amtType"] in ("equity","inflow") and _INV.search(l["type"])}
for e in ents:
    k=e["key"]; rev=(e.get("fin") or {}).get("rev")
    cin=[f for f in flows if f["to"]==k and (k,f["from"]) in _inv]; out=[f for f in flows if f["from"]==k]; inn=[f for f in flows if f["to"]==k]
    e["cash"]={"rev":rev,"circIn":round(sum(f["annual"] for f in cin),2),"circFrom":[[f["from"],f["annual"]] for f in cin],"in":round(sum(f["annual"] for f in inn),2),
               "out":round(sum(f["annual"] for f in out),2),"outTo":[[f["to"],f["annual"]] for f in out]}
data={"asOf":max(e["asOf"] for e in ents),"ents":ents,"links":links,"hubs":hubs,"amt":AMT,"checks":checks,"cycles":cycles,"flows":flows}
# 使用者指引：network template 旁邊若有 guide_template.html，就一併產生 guide.html（公司清單隨資料更新）
GT=os.path.join(os.path.dirname(os.path.abspath(TPL)),"guide_template.html")
if os.path.exists(GT):
    gd={"asOf":data["asOf"],"ents":[{"entity":e["entity"],"ticker":e["ticker"],"accent":e["accent"],"file":e["file"],"asOf":e["asOf"],"nodes":e["nodes"]} for e in ents]}
    open(os.path.join(os.path.dirname(os.path.abspath(OUT)),"guide.html"),"w",encoding="utf-8").write(open(GT,encoding="utf-8").read().replace("/*__GUIDE__*/null",json.dumps(gd,ensure_ascii=False).replace("</","<\\/")))
    data["guide"]="guide.html"; print("📖 已產生使用者指引 guide.html")
tpl=open(TPL,encoding="utf-8").read()
if "/*__DATA__*/null" not in tpl: sys.exit("network template 缺少 /*__DATA__*/null 佔位符")
open(OUT,"w",encoding="utf-8").write(tpl.replace("/*__DATA__*/null",json.dumps(data,ensure_ascii=False).replace("</","<\\/")))
multi=sorted([h for h in hubs if h["deg"]>=2],key=lambda h:-h["deg"])
print(f"✅ 已輸出 {OUT}｜實體 {len(ents)}、關係 {len(links)}、交易對手 {len(hubs)}、跨 ≥2 實體樞紐 {len(multi)}")
for h in multi[:10]: print("  ",h["deg"],h["key"],"、".join(h["ents"]))
print(f"🔁 跨實體資金閉環：{len(cycles)} 條（列出金額最小一段最大的前 5 條）")
for c in cycles[:5]: print("   "," → ".join(f"{e['from']}［{e['short'] if e['amt'] is not None else '金額未揭露'}］" for e in c["edges"]),"→",c["path"][0])
nc=[c for c in checks if c["status"]=="待確認"]
print(f"🔎 跨實體一致性檢查：{len(checks)} 組，其中一致 {sum(c['status']=='一致' for c in checks)}、已說明 {sum(c['status']=='已說明' for c in checks)}、待確認 {len(nc)}、單邊記載 {sum(c['status']=='單邊' for c in checks)}")
for c in checks:
    if c["status"]=="單邊": print("   ➖ 單邊",c["cp"],"｜",c["items"][0]["name"],c["items"][0]["short"])
for c in nc: print("   ⚠️",c["kind"],c["cp"],"；".join(c["flags"]),"｜"," vs ".join(f"{i['ent']}：{i['short']}（{AMT.get(i['amtType'],'')}，{i['date']}）" for i in c["items"]))
