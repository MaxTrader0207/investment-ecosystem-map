#!/usr/bin/env python3
"""把 tpl2.html（壓力測試的獨立版）轉成可嵌進 network_template.html 的片段：
   <template id="stress-tpl">（樣式＋版面，放進 shadow DOM，不和主頁的樣式互相影響）與 <script id="stress-js">。
   用法：python3 embed.py tpl2.html network_template.html"""
import re, sys
src, net = sys.argv[1], sys.argv[2]
t = open(src, encoding='utf-8').read()
css = re.search(r'<style>\n(.*?)</style>', t, re.S).group(1)
body = re.search(r'<div class="page">\n(.*?)</div>\n<div class="tip" id="tip"></div>\n<script>|<div class="page">\n(.*?)</div>\n<script>', t, re.S)
body = body.group(1) or body.group(2)
js = re.search(r'<script>\n(.*?)</script>', t, re.S).group(1)

# —— 樣式：沿用主頁的顏色變數與字體縮放 ——
css = re.sub(r':root\{[^}]*\}\n', '', css, count=1)
css = re.sub(r'html,body\{[^}]*\}', ':host{display:block;color:var(--text);font-size:calc(15px*var(--fs,1));line-height:1.6;--r:var(--st-r,#f87171);--y:var(--st-y,#fbbf24);--g:var(--st-g,#4ade80)}', css, count=1)
css = re.sub(r'\.page\{[^}]*\}', '.page{padding:0}', css, count=1)
css = re.sub(r'h1\{[^}]*\}h1 small\{[^}]*\}\n', '', css, count=1)
css = css.replace('position:sticky;top:0;z-index:5;', '')
css = re.sub(r'\.tip\{[^}]*\}\n', '', css)
css = re.sub(r'font-size:(\d+(?:\.\d+)?)px', r'font-size:calc(\1px*var(--fs,1))', css)
css = css.replace('.three{grid-template-columns:1fr}.assume{position:static}', '.three{grid-template-columns:1fr}')
css = css.replace('.page{padding:14px 12px 40px}', '')
assert ':root' not in css and 'html,body' not in css and 'sticky' not in css

# —— 版面 ——
body = re.sub(r'<h1>.*?</h1>\n', '', body, count=1)
assert '<h1' not in body and '<script' not in body

# —— 程式：資料改由主頁的 DATA 組出來；查詢都限定在 shadow root 內 ——
assert js.count('const D=/*DATA*/;') == 1
js = js.replace('const D=/*DATA*/;', '''const AI=(DATA.extras&&DATA.extras.aiRev)||{};
const D={asOf:DATA.asOf,F:DATA.flows,DU:DATA.due||[],GU:DATA.guar||[],H:DATA.holders||{},BN:(DATA.extras&&DATA.extras.bottlenecks)||[],
 E:Object.fromEntries(DATA.ents.map(e=>[e.key,{n:e.entity,rev:e.fin&&e.fin.rev,cash:e.fin&&e.fin.cash,g:e.fin&&e.fin.growth&&e.fin.growth.ttm,cn:e.scen&&e.scen.cn,capex:e.scen&&e.scen.capex,debt:e.debt||null,ai:AI[e.key]&&AI[e.key].v}]))};''')
assert js.count('$=s=>document.querySelector(s)') == 1
js = js.replace('$=s=>document.querySelector(s)', '$=s=>root.querySelector(s)')
js = js.replace('document.querySelectorAll(', 'root.querySelectorAll(')
assert 'document.' not in js, re.findall(r'.{30}document\..{30}', js)
js = js.replace("'stress_tpl_v3'", "'ecomap_stress_v1'")
for a, b in (('fill="#e6edf3"', 'style="fill:var(--text)"'), ('fill="#8b9bb0"', 'style="fill:var(--muted)"'), ('stroke="#243041"', 'style="stroke:var(--line)"'),
             ('''fill="${y===Y?'#e6edf3':'#8b9bb0'}"''', '''style="fill:${y===Y?'var(--text)':'var(--muted)'}"''')):
    assert a in js, a
    js = js.replace(a, b)
assert '#e6edf3' not in js and '#8b9bb0' not in js and '#243041' not in js

tpl = ('<template id="stress-tpl"><style>\n' + css + '</style>\n<div class="page">\n' + body + '</div></template>')
script = ('<script id="stress-js">\n/* ---------- 付款高峰壓力測試：樣式與版面在 <template id="stress-tpl">，放進 shadow DOM ---------- */\n(function(){\n'
          ' const host=document.getElementById(\'stress\'),tp=document.getElementById(\'stress-tpl\');if(!host||!tp||!host.attachShadow)return;\n'
          ' const root=host.attachShadow({mode:\'open\'});root.appendChild(tp.content.cloneNode(true));\n' + js + '})();\n</script>')
n = open(net, encoding='utf-8').read()
# 重複執行時先拿掉舊片段
n = re.sub(r'<template id="stress-tpl">.*?</template>\n', '', n, flags=re.S)
n = re.sub(r'<script id="stress-js">.*?</script>\n', '', n, flags=re.S)
A = '<div class="brief" id="stress"></div>\n'
assert n.count(A) == 1, '找不到 #stress 區塊'
n = n.replace(A, A + tpl + '\n')
B = '<script id="sec-js">'
assert n.count(B) == 1
n = n.replace(B, script + '\n' + B)
open(net, 'w', encoding='utf-8').write(n)
print('ok', len(tpl), len(script))
