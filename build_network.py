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
        "fin":(dict(D["fin"],src=[[S[x][0],S[x][1]] for x in D["fin"].get("src",[]) if x in S],
                    cashSrc=[[S[x][0],S[x][1]] for x in D["fin"].get("cashSrc",[]) if x in S],burnSrc=[[S[x][0],S[x][1]] for x in D["fin"].get("burnSrc",[]) if x in S],
                    rep=(dict(D["fin"]["rep"],src=[[S[x][0],S[x][1]] for x in D["fin"]["rep"].get("src",[]) if x in S]) if isinstance(D["fin"].get("rep"),dict) else None),circEst=(dict(D["fin"]["circEst"],src=[[S[x][0],S[x][1]] for x in D["fin"]["circEst"].get("src",[]) if x in S]) if isinstance(D["fin"].get("circEst"),dict) else None)) if isinstance(D.get("fin"),dict) else None),
        "mkt":(dict(D["mkt"],src=[[S[k][0],S[k][1]] for k in D["mkt"].get("src",[]) if k in S]) if isinstance(D.get("mkt"),dict) else None),
        "dues":[dict(x,src=[[S[k][0],S[k][1]] for k in x.get("src",[]) if k in S]) for x in D.get("dues",[])],
        "rk":{"n":sum(1 for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty")),
              "eq":[n["amt"] for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and n.get("amtType","equity")=="equity" and n.get("direction","out")!="in" and n.get("amt") is not None and not n.get("excludeFromSum") and not n.get("per")],
              "dep":[l.get("dep") for l in D.get("loops",[]) if l.get("dep")],
              "guar":sum(1 for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and (n.get("guarantee") or "擔保" in n.get("type","") or n.get("amtType")=="liability" or any(r["k"]=="fin" for r in n.get("risks",[])))),
              "unc":sum(1 for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and (n.get("unconfirmed") or any(r["k"]=="exec" for r in n.get("risks",[])))),
              "gamt":sum((n.get("guarAmt") if n.get("guarAmt") is not None else (n.get("amt") or 0)) for n in D["nodes"] if not cats.get(n["cat"],{}).get("counterparty") and not n.get("excludeFromSum")
                         and (n.get("guarAmt") is not None or n.get("amtType")=="liability" or ("擔保" in n.get("type","") and n.get("amtType") in ("commitment","none")))),
              "x":{"cn":((D.get("macro") or {}).get("geo") or {}).get("cn"),
                   "capex":round(sum(n["amt"] for n in D["nodes"] if n.get("amtType")=="capex" and n.get("amt") is not None and (n.get("per")=="year" or n["id"]=="capex")),2) or None,
                   "gonly":round(sum((n.get("guarAmt") if n.get("guarAmt") is not None else (n.get("amt") or 0)) for n in D["nodes"] if not n.get("excludeFromSum") and n.get("amtType")!="liability" and (n.get("guarAmt") is not None or n.get("guarantee") or "擔保" in n.get("type",""))),2),
                   "guar":[[n["name"],(n.get("guarAmt") if n.get("guarAmt") is not None else n.get("amt")),n.get("status",""),str(n.get("date","")),(n.get("term") or {}).get("e")] for n in D["nodes"] if n.get("amtType")!="liability" and (n.get("guarAmt") is not None or n.get("guarantee") or "擔保" in n.get("type",""))],
                   "fund":[[n["name"],n["amt"],str(n.get("date","")),n.get("amtType")] for n in D["nodes"] if n.get("direction")=="in" and n.get("amt") is not None and not n.get("excludeFromSum") and not re.search("股東|持股|採購|銷售|客戶",n.get("type","")) and (n.get("amtType")=="liability" or (n.get("amtType") in ("inflow","equity") and re.search("募資|輪|IPO|增資|發行|配售|股權|入股|特別股|認購|投資|ADR|基金|可轉|債|貸款|融資",n.get("type","")+n["name"])))],
                   "pol":[[str(d0),nm0,tx0[:150],(S[sk[0]][1] if sk and sk[0] in S else "")] for d0,nm0,tx0,sk in [(n.get("date",""),n["name"],n.get("amtText","") or n.get("status",""),n.get("src",[])) for n in D["nodes"]]+[(v.get("d",""),v.get("t",""),v.get("x",""),v.get("src",[])) for v in D.get("events",[])]+[(M["asOf"],"地緣政治面向",((D.get("macro") or {}).get("geo") or {}).get("basis",""),((D.get("macro") or {}).get("geo") or {}).get("src",[]))]],
                   "fs":[[n["name"],n["amt"],str(n.get("date","")),n.get("amtType"),n.get("type","")] for n in D["nodes"] if n.get("amt") is not None and not re.search("股東|持股|採購|銷售|客戶",n.get("type","")) and ((n.get("direction")=="in" and n.get("amtType")=="liability") or (n.get("direction")=="in" and n.get("amtType") in ("inflow","equity") and re.search("募資|輪|IPO|增資|發行|配售|股權|入股|特別股|認購|投資|ADR|基金|可轉|債|貸款|融資",n.get("type","")+n["name"])) or (n.get("amtType")=="project" and re.search("SPV|特殊目的|合資|JV|融資平台|售後回租",n.get("type","")+n["name"]) and re.search("債|融資|貸款|信貸|Blue Owl|PIMCO|Apollo|Blackstone",n.get("amtText","")+n.get("type","")+n["name"])))],
                   "rates":[[n.get("date",""),n["name"],n["rate"]] for n in D["nodes"] if isinstance(n.get("rate"),(int,float))],
                   "txt":[[str(n.get("date","")),n["name"],(n.get("status","")+"｜"+n.get("amtText",""))[:240],n.get("sig")] for n in D["nodes"]]+[[str(v.get("d","")),v.get("t",""),v.get("x","")[:240],v.get("sig")] for v in D.get("events",[])],"ps":D.get("paySched")},
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
    rk=e.pop("rk"); e["xx"]=rk.pop("x"); st=e["st"]; n=max(rk["n"],15); k=e["key"]; R={}   # 節點少於 15 個時以 15 計，避免資料少的公司占比被放大
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
    # 擔保與或有負債：先扣現金，再與年營收相比（沒有營收的投資機構才退回與股權投資相比）
    ga=rk["gamt"]; fn=e.get("fin") or {}; cash=fn.get("cash"); rev=fn.get("rev")
    net=max(0,ga-cash) if isinstance(cash,(int,float)) else ga
    if ga<=0: gr=0; gb="沒有已揭露金額的擔保或負債節點；"
    else:
        gb=f"擔保與負債金額 {fmtb(ga)}"+(f"，扣除現金 {fmtb(cash)} 後淨額 {fmtb(net)}" if isinstance(cash,(int,float)) else "（未取得現金資料，未扣除）")
        if isinstance(rev,(int,float)) and rev>0: gr=min(1,net/rev); gb+=f"，相當於年營收 {fmtb(rev)} 的 {net/rev*100:.0f}%（達 100% 即滿分，占六成權重）；"
        else: gr=net/(net+tot) if net>0 else 0; gb+=f"，相當於「擔保負債＋股權類投資」的 {gr*100:.0f}%（無營收資料，占六成權重）；"
    R["fin"]=(_cap(0.6*gr*100+0.4*_flag(rk["guar"],n,0.20)),gb+f"{rk['guar']} 個節點有擔保、負債或財務風險旗標（占四成權重）")
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
        dims.append({"k":key,"n":name,"w":0,"s":r[0] if r else None,"b":r[1] if r else (rk["macro"].get(key,{}).get("basis") or "待補資料：需要另外查證公開數據後才能評分"),"src":list(r[2]) if r and len(r)>2 else [],"na":(not r) and str(rk["macro"].get(key,{}).get("basis") or "").startswith("不適用")})
    e["risk"]={"dims":dims}
_W=_weights(ents)
for e in ents:
    dims=e["risk"]["dims"]
    for d in dims: d["w"]=_W[d["k"]]
    cov=sum(d["w"] for d in dims if d["s"] is not None)
    e["risk"].update({"cov":int(round(cov)),"total":int(round(sum(d["s"]*d["w"] for d in dims if d["s"] is not None)/cov)) if cov else None})
    # 燈號：總分 45 以上紅、30–44 黃、29 以下綠；任一面向達 ALERT 分（單項警示）時，總燈號至少升一級，避免嚴重的單一風險被平均稀釋
    t=e["risk"]["total"]; base=0 if t is None else 3 if t>=45 else 2 if t>=30 else 1
    al=[[d["n"],d["s"]] for d in sorted(dims,key=lambda d:-(d["s"] or 0)) if d["s"] is not None and d["s"]>=ALERT and d["k"] not in ("info","fx")]   # 不觸發警示的兩個面向：資訊可信度反映的是資料品質；匯率面向量的是本國以外營收占比，出口型公司天生就高，屬於曝險而不是惡化
    e["risk"].update({"base":base,"alert":al,"light":min(3,base+1) if al and base else base})
_rank=sorted([e for e in ents if e["risk"]["total"] is not None],key=lambda e:-e["risk"]["total"])
for i,e in enumerate(_rank): e["risk"]["rank"]=1+sum(1 for x in _rank if x["risk"]["total"]>e["risk"]["total"]); e["risk"]["of"]=len(_rank)
cycles=cycles[:40]
# ---------- 年化金流：有揭露年期（term）或實際年金額（annual）的合約 → 付款方→收款方的每年金額 ----------
# 用於「循環融資占營收」「每年現金缺口」「付款時程」「情境試算」。同一對付款方／收款方兩邊檔案都有時，以付款方那份為準。
# 付款分布：付款方若揭露了逐年義務表（data.json 的 paySched），就用它的形狀分配各合約的金額；否則留給前端選擇平均攤提或前低後高
_PS={e["key"]:(e.get("xx") or {}).get("ps") for e in ents}
def _sched(payer,tot,s,e_):
    ps=_PS.get(payer)
    if not ps or not tot or not s: return None
    yy=ps.get("y",{}); last=max(int(k) for k in yy); af=ps.get("after") or [0,last]
    w={y:(yy.get(str(y)) if str(y) in yy else (af[0]/max(1,af[1]-last) if last<y<=af[1] else 0)) for y in range(s,e_+1)}
    sw=sum(w.values())
    return {str(y):round(tot*v/sw,2) for y,v in w.items()} if sw else None
_fl={}
for l in links:
    if l["amtType"] not in ("contract","commitment") or l["amt"] is None or not (l.get("term") or l.get("annual")): continue
    if _INV.search(l["type"]) and not _NOTINV.search(l["type"]): continue
    payer,payee=(l["cp"],l["ent"]) if l["dir"]=="in" else (l["ent"],l["cp"])
    t=l.get("term") or {}; tot=t.get("firm",l["amt"]); yrs=(t["e"]-t["s"]+1) if t else None
    f={"from":payer,"to":payee,"annual":round(l["annual"] if l.get("annual") else tot/yrs,2),"total":tot if t else None,"s":t.get("s"),"e":t.get("e"),"name":l["name"],"short":l["short"],"by":l["ent"],"src":l["src"][:1],"actual":bool(l.get("annual"))}
    _sc=_sched(payer,tot if t else None,t.get("s"),t.get("e"))
    if _sc: f["sched"]=_sc
    k=(payer,payee)
    if k not in _fl or (l["ent"]==payer and _fl[k]["by"]!=payer): _fl[k]=f
flows=sorted(_fl.values(),key=lambda f:-f["annual"])
_inv={(l["ent"],l["cp"]) for l in links if l["dir"]!="in" and l["amt"] is not None and not _DEAD.search(l["type"]) and (l["amtType"]=="equity" or (l["amtType"] in ("commitment","project") and _INV.search(l["type"]) and not _NOTINV.search(l["type"])))}
_inv|={(l["cp"],l["ent"]) for l in links if l["dir"]=="in" and l["amt"] is not None and l["amtType"] in ("equity","inflow") and _INV.search(l["type"])}
for e in ents:
    k=e["key"]; rev=(e.get("fin") or {}).get("rev")
    cin=[f for f in flows if f["to"]==k and (k,f["from"]) in _inv]; out=[f for f in flows if f["from"]==k]; inn=[f for f in flows if f["to"]==k]
    e["cash"]={"rev":rev,"run":(e.get("fin") or {}).get("revRun"),"circIn":round(sum(f["annual"] for f in cin),2),"circFrom":[[f["from"],f["annual"]] for f in cin],"in":round(sum(f["annual"] for f in inn),2),
               "out":round(sum(f["annual"] for f in out),2),"outTo":[[f["to"],f["annual"]] for f in out]}
# ---------- 預警指標／變動紀錄／本期結論 ----------
import datetime as _dt
ASOF=max(e["asOf"] for e in ents); _name={e["key"]:e["entity"] for e in ents}
def _days(d):
    try:
        p=[int(x) for x in str(d).split("-")]+[1,1]; return (_dt.date(*[int(x) for x in ASOF.split("-")])-_dt.date(p[0],p[1] if len(str(d))>4 else 12,p[2] if len(str(d))>7 else 28)).days
    except Exception: return 10**6
_X={}
for e in ents: _X[e["key"]]=e.pop("xx")
for e in ents: e["scen"]={"cn":_X[e["key"]]["cn"],"capex":_X[e["key"]]["capex"]}
for e in ents:    # 缺口靠誰補：近 12 個月的募資與舉債；到期事項與擔保
    fu=sorted([f for f in _X[e["key"]]["fund"] if 0<=_days(f[2])<=365],key=lambda f:-f[1])
    e["fund"]={"tot":round(sum(f[1] for f in fu),1),"top":[[f[0],f[1],f[3]] for f in fu[:3]]}
# 資金來源結構：近 24 個月的募資與舉債，依名稱與型態分類
_FS=[("off","私募信貸與表外",re.compile("DDTL|私募|SPV|特殊目的|售後回租|租約|合資|JV|融資平台|Blue Owl|Apollo|Blackstone|PIMCO|擔保貸款|保證金貸款|過橋|質押")),("conv","可轉債",re.compile("可轉")),
     ("bond","公開債券",re.compile("債券|票據|公司債|發債")),("loan","其他借款",None),("eq","股權",None)]
for e in ents:
    mix={k:0 for k,_,_ in _FS}; items=[]
    for nm0,a,d0,at,ty in _X[e["key"]]["fs"]:
        if not (0<=_days(d0)<=730): continue
        s=nm0+ty; c=("conv" if "可轉" in s else "bond" if re.search("債|票據",s) else "eq") if at in ("inflow","equity") else (next((k for k,_,rx in _FS if rx and rx.search(s)),None) or ("loan" if at=="liability" else "off"))
        mix[c]+=a; items.append([nm0,a,c])
    tot=sum(mix.values()); e["fs"]={"tot":round(tot,1),"mix":{k:round(v,1) for k,v in mix.items()},"top":sorted(items,key=lambda x:-x[1])[:4]} if tot>0 else None
# 主權與政策層：從節點與事件文字歸類
_POL=[("出口管制與許可",re.compile("出口管制|出口許可|出口限制|許可機制|年度許可|需出口許可|實體清單|禁售|H20|MI308|晶片禁令")),("關稅",re.compile("關稅")),
      ("政府入股與補助",re.compile("政府入股|政府持股|商務部|CHIPS|晶片法|政府補助|補助款|國家基金|大基金|國資")),
      ("主權基金入股",re.compile("主權基金|PIF|MGX|Mubadala|QIA|GIC|淡馬錫|Temasek|HUMAIN")),
      ("國安審查與強制分拆",re.compile("CFIUS|國安|國家安全|強制分拆|分拆成合資|法律允許上限|安全審查"))]
policy=[]
for k,v in _X.items():
    seen=set()
    for d0,nm0,tx0,u in v["pol"]:
        for cat,rx in _POL:
            if cat=="主權基金入股" and re.search("MGX|PIF",k): continue
            if rx.search(nm0+tx0) and (cat,nm0) not in seen: seen.add((cat,nm0)); policy.append({"cat":cat,"ent":_name[k],"key":k,"d":d0,"n":nm0,"x":tx0,"u":u})
policy.sort(key=lambda p:(p["cat"],p["d"]),reverse=True)
# 實體瓶頸與歷史對照：人工維護的 extras.json（與 changelog.json 同一層）；現況比率由資料計算
_EXF=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(FILES[0]))),"extras.json")
extras=json.load(open(_EXF,encoding="utf-8")) if os.path.exists(_EXF) else {}
# 實體瓶頸對應到公司：affects 文字裡點名的已建檔公司
for e in ents: e["phy"]=[]
for _b in extras.get("bottlenecks",[]):
    _a=_b.get("affects","").replace("xAI","SpaceX"); _b["hit"]=[]
    for e in ents:
        _tk=[x for x in re.split(r"[ ／（）()]+",e["key"]+" "+e["entity"]) if len(x)>=2 and x not in ("Group","Alphabet")]
        if any(x in _a for x in _tk):
            _b["hit"].append([e["key"],e["entity"]]); e["phy"].append([_b["n"],_b.get("light",0)])
# 資料新鮮度：以建置當天為準，營收與現金的基準日超過 200 天（約兩季）、市值超過 45 天就標示過期；沒填基準日的標示未標示
import datetime as _dt
def _age(d,lim):
    try:
        p=[int(x) for x in str(d).split("-")]+[1,1]; n=(_dt.date.today()-_dt.date(p[0],p[1],p[2])).days
        return [str(d),n,3 if n>lim else 2 if n>lim*0.75 else 1]
    except Exception: return None
fresh=[]
for e in ents:
    _f=e.get("fin") or {}; _m=e.get("mkt") or {}
    r={"key":e["key"],"entity":e["entity"],"rev":(_age(_f.get("period"),200) if _f.get("rev") is not None else None),"revNo":_f.get("rev") is not None and not _f.get("period"),
       "cash":(_age(_f.get("cashDate"),200) if _f.get("cash") is not None else None),"cashNo":_f.get("cash") is not None and not _f.get("cashDate"),
       "mkt":(_age(_m.get("date"),45) if _m.get("cap") is not None else None),"chk":_age(e["asOf"],120)}
    _n=str(_f.get("note") or ""); r["basis"]=("" if _f.get("rev") is None else "最近四季（含推算）" if ("最近四季" in _n and ("推算值" in _n or "含估算" in _n)) else "最近四季" if "最近四季" in _n else "單季年化" if ("× 4" in _n or "×4" in _n) else "期間年化" if "年化" in _n else "全年估計" if ("估計" in _n or "指引" in _n) else "財年實績")
    r["stale"]=[n for n,k in (("營收","rev"),("現金","cash"),("市值","mkt")) if r[k] and r[k][2]==3]+[n for n,k in (("營收","revNo"),("現金","cashNo")) if r[k]]
    fresh.append(r)
_stale=[r for r in fresh if r["stale"]]
if _stale: print("⚠️  資料過期或未標示基準日："+"；".join(r["entity"]+"（"+"、".join(r["stale"])+"）" for r in _stale))
vfnow=sorted([{"ent":e["entity"],"key":e["key"],"fin":_X[e["key"]]["gonly"],"rev":(e.get("fin") or {}).get("rev")} for e in ents if _X[e["key"]]["gonly"]>0 and (e.get("fin") or {}).get("rev")],key=lambda x:-x["fin"]/x["rev"])
due=[dict(x,ent=e["entity"],key=e["key"]) for e in ents for x in e.pop("dues",[])]
guar=sorted([{"ent":_name[k],"key":k,"name":g[0],"amt":g[1],"status":g[2],"date":g[3],"end":g[4]} for k,v in _X.items() for g in v["guar"]],key=lambda g:-(g["amt"] or 0))
_yrs=list(range(int(ASOF[:4]),int(ASOF[:4])+11))
_tot={y:sum((f["sched"].get(str(y),0) if f.get("sched") else f["total"]/(f["e"]-f["s"]+1)) for f in flows if f.get("s") and f["s"]<=y<=f["e"]) for y in _yrs}
_pk=max(_tot.values()) if _tot else 0; _pky=[y for y in _yrs if _pk and _tot[y]>=0.95*_pk]
_gap=sorted([(e["cash"]["out"]/e["cash"]["rev"],e) for e in ents if e["cash"]["rev"] and e["cash"]["out"]],key=lambda x:-x[0])
_circ=sorted([(e["cash"]["circIn"]/e["cash"]["rev"],e) for e in ents if e["cash"]["rev"] and e["cash"]["circIn"]],key=lambda x:-x[0])
_recent=[(k,d,n,x,s) for k,v in _X.items() for d,n,x,s in v["txt"] if 0<=_days(d)<=120]
_RE_CUT=re.compile("(募資|輪|承諾|合約|訂單|投資|資本支出|估值|收購|專案|建廠).{0,24}(下修|降至|縮減|削減|延後|展延|暫停|終止|否決)|(下修|縮減|削減|延後|展延|暫停).{0,12}(募資|承諾|合約|訂單|投資|資本支出|專案)"); _RE_WAR=re.compile("(權證|擔保|保證|質押|備援承購).{0,18}(修改|調整|重訂|觸發|追加|擴大|增額|提高)")
# 節點或事件的 sig 欄位是人工確認的結果："cut"＝募資或承諾下修、展延，"terms"＝權證、擔保或質押條件變動，"none"＝確認不是。只有確認過的才計數；文字比對到但還沒標記的另列為待確認。同一家同一天只算一則
def _sig(kind,RE):
    ok,cand={},{}
    for k,d,n,x,s in _recent:
        if s==kind: ok.setdefault((k,d),n)
        elif s is None and RE.search(n+x): cand.setdefault((k,d),n)
    return [(k,d,n) for (k,d),n in ok.items()],[(k,d,n) for (k,d),n in cand.items() if (k,d) not in ok]
(_cut,_cutq),(_war,_warq)=_sig("cut",_RE_CUT),_sig("terms",_RE_WAR)
_rates=sorted([(r,_name[k],n,d) for k,v in _X.items() for d,n,r in v["rates"] if 0<=_days(d)<=365],reverse=True)
_gtot=round(sum(v["gonly"] for v in _X.values()),1); _reds=[e for e in ents if e["risk"]["light"]==3]
def _lt(v,red,yel): return 3 if v>=red else 2 if v>=yel else 1
watch=[]
if _gap: g,ge=_gap[0]; watch.append({"n":"承諾支出相對營收","v":f"{ge['entity']} {g:.1f} 倍","x":round(g,2),"light":_lt(g,2,1),"rule":"最高者達 2 倍亮紅燈、1 倍亮黃燈","detail":"、".join(f"{e['entity']} {r:.1f} 倍" for r,e in _gap[:3])+("｜若改用最新一季年化營收："+"、".join(f"{e['entity']} {e['cash']['out']/e['cash']['run']:.1f} 倍" for r,e in _gap[:3] if e["cash"].get("run")) if any(e["cash"].get("run") for r,e in _gap[:3]) else "")})
if _circ: c,ce=_circ[0]; watch.append({"n":"循環收入占營收","v":f"{ce['entity']} {c*100:.0f}%","x":round(c*100,1),"light":_lt(c,0.2,0.1),"rule":"最高者達 20% 亮紅燈、10% 亮黃燈","detail":"、".join(f"{e['entity']} {r*100:.0f}%" for r,e in _circ[:3])})
if _pky: yl=_pky[0]-int(ASOF[:4]); watch.append({"n":"距離付款高峰","v":f"{_pky[0]}–{_pky[-1]} 年" if len(_pky)>1 else f"{_pky[0]} 年","x":yl,"dir":-1,"light":3 if yl<=1 else 2 if yl<=3 else 1,"rule":"高峰在 1 年內亮紅燈、3 年內亮黃燈","detail":f"高峰每年約 {fmtb(_pk)}（只含有揭露年期的合約）"})
watch.append({"n":"新債票息","v":f"{_rates[0][0]:g}%（{_rates[0][1]}）" if _rates else "尚無資料","x":(_rates[0][0] if _rates else None),"light":(_lt(_rates[0][0],9,7) if _rates else 0),"rule":"近 12 個月新債最高票息達 9% 亮紅燈、7% 亮黃燈","detail":"；".join(f"{a} {n} {r:g}%" for r,a,n,d in _rates[:3]) if _rates else "負債節點尚未填入票息（rate 欄位）"})
watch.append({"n":"募資或承諾下修、展延","v":f"{len(_cut)} 則"+(f"（另 {len(_cutq)} 則待確認）" if _cutq else ""),"x":len(_cut),"light":_lt(len(_cut),3,1),"rule":"近 120 天人工確認過的達 3 則亮紅燈、1 則亮黃燈；同一家同一天算一則，文字比對到但未確認的不計","detail":("；".join(f"{_name[k]}：{n}" for k,d,n in sorted(_cut,key=lambda x:x[1],reverse=True)[:4]) or "沒有確認過的事件")+("｜待確認："+"；".join(f"{_name[k]}：{n}" for k,d,n in _cutq[:3]) if _cutq else "")})
watch.append({"n":"權證或擔保條件變動","v":f"{len(_war)} 則"+(f"（另 {len(_warq)} 則待確認）" if _warq else ""),"x":len(_war),"light":_lt(len(_war),2,1),"rule":"近 120 天人工確認過的達 2 則亮紅燈、1 則亮黃燈；含質押與保證金貸款條件，文字比對到但未確認的不計","detail":("；".join(f"{_name[k]}：{n}" for k,d,n in _war[:4]) or "沒有確認過的事件")+("｜待確認："+"；".join(f"{_name[k]}：{n}" for k,d,n in _warq[:3]) if _warq else "")})
# 變動紀錄：與上一期的狀態比較（同一期重建不會覆蓋比較基準）
def _snap(D0):
    return {"ents":{e["key"]:{"n":e["entity"],"t":e["risk"]["total"] if e.get("risk") else None,"l":e["risk"]["light"] if e.get("risk") else None,"nodes":e["nodes"],"cap":(e.get("mkt") or {}).get("cap"),
                              "gap":round(e["cash"]["out"]-e["cash"]["rev"],1) if e.get("cash") and e["cash"].get("rev") and e["cash"].get("out") else None} for e in D0["ents"]},
            "links":{l["ent"]+"｜"+l["name"]:[l["amt"],l["short"],l["date"]] for l in D0["links"]}}
_cur=_snap({"ents":ents,"links":links})
LOGF=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(FILES[0]))),"changelog.json")
_log=json.load(open(LOGF,encoding="utf-8")) if os.path.exists(LOGF) else {"log":[],"base":None,"cur":None}
if not _log.get("cur"):
    _pf=os.environ.get("IEM_PREV") or OUT
    if os.path.exists(_pf):
        _m=re.search(r"DATA\s*=\s*(\{.*\})\s*;",open(_pf,encoding="utf-8").read())
        if _m:
            try: _pd=json.loads(_m.group(1)); _log["cur"]={"d":_pd["asOf"],"snap":_snap(_pd)}
            except Exception: pass
if _log.get("cur") and _log["cur"]["d"]!=ASOF: _log["base"]=_log["cur"]
_auto=[]; _LN={1:"綠燈",2:"黃燈",3:"紅燈"}
if _log.get("base"):
    B=_log["base"]["snap"]; be,ce_=B["ents"],_cur["ents"]; bl,cl_=B["links"],_cur["links"]
    for k in ce_:
        if k not in be: _auto.append({"t":"新增公司","e":ce_[k]["n"],"x":f"新建 Dashboard（{ce_[k]['nodes']} 個節點，風險 {ce_[k]['t']} 分、{_LN.get(ce_[k]['l'],'')}）","why":"擴充追蹤範圍"})
    for k in be:
        if k not in ce_: _auto.append({"t":"移除公司","e":be[k]["n"],"x":"不再追蹤","why":"資料檔已移除"})
    _touched=set()
    for lk,(a,s,d) in cl_.items():
        ent,nm=lk.split("｜",1)
        if ent not in be: continue
        if lk not in bl: _auto.append({"t":"新增節點","e":_name.get(ent,ent),"x":f"{nm}：{s or '金額未揭露'}","why":f"新查證的資料（節點日期 {d or '未註明'}）"}); _touched.add(ent)
        elif (bl[lk][0] or 0)!=(a or 0) and abs((bl[lk][0] or 0)-(a or 0))>=0.05: _auto.append({"t":"金額更新","e":_name.get(ent,ent),"x":f"{nm}：{bl[lk][1] or '未揭露'} → {s or '未揭露'}","why":f"資料更新（節點日期 {bl[lk][2] or '未註明'} → {d or '未註明'}）"}); _touched.add(ent)
    for lk in bl:
        ent,nm=lk.split("｜",1)
        if ent in ce_ and lk not in cl_: _auto.append({"t":"移除節點","e":_name.get(ent,ent),"x":f"{nm}（原 {bl[lk][1] or '未揭露'}）","why":"節點已合併、更名或刪除"}); _touched.add(ent)
    for k in ce_:
        if k in be and be[k]["t"] is not None and ce_[k]["t"] is not None and (be[k]["t"]!=ce_[k]["t"] or be[k]["l"]!=ce_[k]["l"]):
            _auto.append({"t":"燈號變動" if be[k]["l"]!=ce_[k]["l"] else "風險分數","e":ce_[k]["n"],"x":f"{be[k]['t']} → {ce_[k]['t']} 分"+(f"，{_LN.get(be[k]['l'],'')} → {_LN.get(ce_[k]['l'],'')}" if be[k]["l"]!=ce_[k]["l"] else ""),
                          "why":"該公司的節點資料有更新" if k in _touched else "計分公式調整，或因全體公司分布改變使權重自動調整"})
        if k in be and be[k].get("cap") and ce_[k].get("cap") and abs(ce_[k]["cap"]/be[k]["cap"]-1)>=0.02:
            _auto.append({"t":"市值","e":ce_[k]["n"],"x":f"{fmtb(be[k]['cap'])} → {fmtb(ce_[k]['cap'])}（{(ce_[k]['cap']/be[k]['cap']-1)*100:+.0f}%）","why":"每週依最新收盤價自動更新"})
        if k in be and abs(max(be[k].get("gap") or 0,0)-max(ce_[k].get("gap") or 0,0))>=1:
            _auto.append({"t":"現金缺口","e":ce_[k]["n"],"x":f"每年 {fmtb(max(be[k].get('gap') or 0,0))} → {fmtb(max(ce_[k].get('gap') or 0,0))}","why":"合約或年營收資料有更新"})
    _ord={"新增公司":0,"移除公司":1,"燈號變動":2,"現金缺口":3,"市值":3.5,"金額更新":4,"新增節點":5,"移除節點":6,"風險分數":7}; _auto.sort(key=lambda a:(_ord.get(a["t"],9),a["e"]))
_old=next((x for x in _log["log"] if x["d"]==ASOF),None)
_entry={"d":ASOF,"from":(_log["base"] or {}).get("d"),"auto":_auto,"notes":(_old or {}).get("notes",[])}
_log["log"]=[_entry]+[x for x in _log["log"] if x["d"]!=ASOF]; _log["log"]=_log["log"][:26]; _log["cur"]={"d":ASOF,"snap":_cur}
json.dump(_log,open(LOGF,"w",encoding="utf-8"),ensure_ascii=False)
_bg=((_log["base"] or {}).get("snap") or {}).get("ents",{}); _pr=sum(1 for v in _bg.values() if v.get("l")==3) if _bg else None
watch.append({"n":"紅燈家數","v":f"{len(_reds)}／{len(ents)} 家"+(f"（上期 {_pr} 家）" if _pr is not None else ""),"x":len(_reds),"light":_lt(len(_reds)/len(ents),0.4,0.2),"rule":"紅燈占比達 40% 亮紅燈、20% 亮黃燈","detail":"、".join(e["entity"] for e in sorted(_reds,key=lambda e:e["risk"]["rank"])[:6])})
watch.append({"n":"供應商融資與擔保總額","v":fmtb(_gtot) if _gtot else "無","x":_gtot,"light":_lt(_gtot,100,30),"rule":"全體合計達 $1,000 億亮紅燈、$300 億亮黃燈（不含公司自身的借款）","detail":"、".join(f"{_name[k]} {fmtb(v['gonly'])}" for k,v in sorted(_X.items(),key=lambda kv:-kv[1]["gonly"]) if v["gonly"]>0)[:160] or "沒有已揭露金額的擔保"})
# 預警燈號＝水位＋與上一期相比的方向：惡化時升一級、高檔持平時紅降為黃、改善時降一級；沒有上期數值就只看水位
_bw=((_log["base"] or {}).get("snap") or {}).get("watch") or {}
for w in watch:
    w["lvl"]=w["light"]; w["tr"]=None; _p=_bw.get(w["n"])
    if _p and w.get("x") is not None and _p[0] is not None and w["lvl"]:
        _d=(w["x"]-_p[0])*w.get("dir",1); _tol=max(abs(_p[0])*0.03,1e-9)
        w["tr"]=1 if _d>_tol else -1 if _d<-_tol else 0; w["pv"]=_p[1]
        w["light"]=min(3,w["lvl"]+1) if w["tr"]==1 else max(1,w["lvl"]-1) if w["tr"]==-1 else min(w["lvl"],2)
_log["cur"]["snap"]["watch"]={w["n"]:[w.get("x"),w["v"]] for w in watch}
# 歷史走勢：每一期留一筆（同一天重建會覆蓋當天那筆），供總網路圖畫走勢線；第一次執行時用上一期的快照補一筆
def _hrow(d,E,W):
    T=[v["t"] for v in E.values() if v.get("t") is not None]
    return {"d":d,"red":sum(1 for v in E.values() if v.get("l")==3),"yel":sum(1 for v in E.values() if v.get("l")==2),"grn":sum(1 for v in E.values() if v.get("l")==1),"n":len(E),
            "avg":round(sum(T)/len(T),1) if T else None,"e":{k:[v.get("t"),v.get("l")] for k,v in E.items()},"w":{k:v[0] for k,v in (W or {}).items() if isinstance(v[0],(int,float))}}
_hist=_log.get("hist") or []
if not _hist and _log.get("base"): _hist=[_hrow(_log["base"]["d"],_log["base"]["snap"]["ents"],_log["base"]["snap"].get("watch"))]
_hist=[h for h in _hist if h["d"]!=ASOF]+[_hrow(ASOF,_cur["ents"],_log["cur"]["snap"]["watch"])]
_log["hist"]=sorted(_hist,key=lambda h:h["d"])[-104:]
json.dump(_log,open(LOGF,"w",encoding="utf-8"),ensure_ascii=False)
# 財報日曆：fin.rep={last:上次公布日, next:下次公布日, conf:是否公司已確認}；沒有 next 時以上次公布日加 91 天推估
cal=[]
for e in ents:
    _r=(e.get("fin") or {}).get("rep") or {}
    if not _r.get("last") and not _r.get("next"): cal.append({"key":e["key"],"entity":e["entity"],"last":None,"next":None,"st":"none"}); continue
    _nx=_r.get("next"); _st="conf" if (_nx and _r.get("conf")) else "exp" if _nx else "est"
    if not _nx:
        try: _nx=str(_dt.date.fromisoformat(_r["last"])+_dt.timedelta(days=91))
        except Exception: _nx=None
    cal.append({"key":e["key"],"entity":e["entity"],"last":_r.get("last"),"next":_nx,"st":_st,"days":((_dt.date.fromisoformat(_nx)-_dt.date.today()).days if _nx else None),"src":_r.get("src") or []})
cal.sort(key=lambda c:(c["next"] is None,c["next"] or ""))
# 本期結論：三到五句
_top=sorted(ents,key=lambda e:e["risk"]["rank"])[0]; head=[]
head.append(f"目前追蹤 {len(ents)} 家，其中 {len(_reds)} 家紅燈；有揭露年期的合約付款高峰在 {_pky[0]}"+(f"–{_pky[-1]}" if len(_pky)>1 else "")+f" 年，每年約 {fmtb(_pk)}。" if _pky else f"目前追蹤 {len(ents)} 家，其中 {len(_reds)} 家紅燈。")
if _gap:
    g,ge=_gap[0]; head.append(f"最脆弱的環節是 {ge['entity']}：每年承諾支出約 {fmtb(ge['cash']['out'])}，是年營收的 {g:.1f} 倍，缺口約 {fmtb(ge['cash']['out']-ge['cash']['rev'])} 要靠募資或舉債補上；風險總分最高的是 {_top['entity']}（{_top['risk']['total']} 分）。")
if _circ: c,ce=_circ[0]; head.append(f"循環融資最集中的是 {ce['entity']}：約 {c*100:.0f}% 的年營收來自它自己入股或融資的對象（"+"、".join(_name.get(k,k) for k,_ in ce["cash"]["circFrom"][:2])+"）。")
_rw=[w for w in watch if w["light"]==3]; _wz=[w for w in watch if w["tr"]==1]; _hi=[w for w in watch if w["lvl"]==3]
head.append(f"{len(watch)} 項預警指標中有 {len(_hi)} 項處於紅燈水位"+(f"，其中 {len(_wz)} 項比上期惡化（"+"、".join(w["n"] for w in _wz[:4])+"）" if _wz else ("，沒有比上期惡化的項目" if any(w["tr"] is not None for w in watch) else "；與上期的方向比較從下一期開始"))+"。")
if _entry["from"]:
    _cnt={}; 
    for a in _auto: _cnt[a["t"]]=_cnt.get(a["t"],0)+1
    _new=[a["e"] for a in _auto if a["t"]=="新增公司"]; _lc=[a["e"]+"（"+a["x"].split("，")[-1]+"）" for a in _auto if a["t"]=="燈號變動"]
    head.append(f"與上一期（{_entry['from']}）相比："+("；".join(filter(None,[("新增 "+"、".join(_new)) if _new else "",("燈號變動 "+"、".join(_lc[:4])) if _lc else "",f"金額更新 {_cnt.get('金額更新',0)} 筆、新增節點 {_cnt.get('新增節點',0)} 個" if _cnt.get('金額更新') or _cnt.get('新增節點') else ""])) or "沒有數字變動")+"。")
data={"asOf":ASOF,"ents":ents,"links":links,"hubs":hubs,"amt":AMT,"checks":checks,"cycles":cycles,"flows":flows,"watch":watch,"head":head,"due":due,"guar":guar,"policy":policy,"extras":extras,"fresh":fresh,"vfnow":vfnow,"hist":_log.get("hist",[]),"cal":cal,"chg":[{k:x[k] for k in ("d","from","auto","notes")} for x in _log["log"][:8]]}
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
