#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sondagem temporária dos sites com captação baixa. Grava diag/resultado.json."""
import json, os, re, sys, time, traceback
from urllib.parse import urljoin, urlparse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "monitor"))
import monitor as m
import render_js

cfg = json.load(open(os.path.join(ROOT, "config", "sites.json"), encoding="utf-8"))
SITES = {s["id"]: s for s in cfg["sites"]}
OUT = {}
S = requests.Session()

def props_de(urls, sid):
    return sorted({u for u in urls if m.is_property_url(u, SITES[sid])})

def get(url, **kw):
    t = time.time()
    try:
        r = S.get(url, headers=m.HEADERS, timeout=25, allow_redirects=True, **kw)
        txt = r.text
        return {"status": r.status_code, "final": r.url, "len": len(txt),
                "titulo": (re.search(r"<title[^>]*>([^<]{0,120})", txt, re.I) or [None, None])[1],
                "seg": round(time.time() - t, 1)}, txt
    except Exception as e:
        return {"erro": str(e)[:200], "seg": round(time.time() - t, 1)}, ""

def links(html, base):
    out = set()
    for h in re.findall(r'href=["\']([^"\'#]+)', html):
        f = urljoin(base, h)
        if urlparse(f).netloc == urlparse(base).netloc:
            out.add(f)
    return out

def bloco(nome, fn):
    t = time.time()
    try:
        OUT[nome] = fn()
    except Exception:
        OUT[nome] = {"excecao": traceback.format_exc()[-600:]}
    OUT[nome] = OUT[nome] if isinstance(OUT[nome], dict) else {"v": OUT[nome]}
    OUT[nome]["_seg"] = round(time.time() - t, 1)
    json.dump(OUT, open(os.path.join(ROOT, "diag", "resultado.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("ok", nome, flush=True)

os.makedirs(os.path.join(ROOT, "diag"), exist_ok=True)

# 1) Auxiliadora: sitemap, paginação e chamadas de API
def aux():
    base = "https://www.auxiliadorapredial.com.br"
    r = {}
    rb, txt = get(base + "/robots.txt"); r["robots"] = txt[:800]
    for sm in m.discover_sitemaps(base, S)[:6]:
        info, t = get(sm)
        locs = re.findall(r"<loc>\s*([^<\s]+)", t)
        r.setdefault("sitemaps", {})[sm] = {**info, "locs": len(locs), "ex": locs[:5],
                                            "imovel": sum(1 for u in locs if "/imovel/" in u)}
    pg = render_js._pagina()
    api = []
    def on_resp(resp):
        try:
            ct = resp.headers.get("content-type", "")
            if "json" in ct and len(api) < 40:
                api.append({"url": resp.url[:300], "status": resp.status, "metodo": resp.request.method,
                            "post": (resp.request.post_data or "")[:400]})
        except Exception:
            pass
    pg.on("response", on_resp)
    url = base + "/comprar/residencial/rs+porto-alegre+petropolis"
    pg.goto(url, timeout=45000, wait_until="domcontentloaded")
    pg.wait_for_timeout(7000)
    antes = len(props_de(pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)"), "auxiliadora"))
    for _ in range(12):
        pg.mouse.wheel(0, 5000); pg.wait_for_timeout(1300)
    depois = len(props_de(pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)"), "auxiliadora"))
    body = pg.inner_text("body")
    r["petropolis"] = {"props_antes_rolar": antes, "props_depois_rolar": depois,
                       "total_texto": re.findall(r"[\d\.]+\s+(?:im[oó]veis|resultados|encontrad)", body, re.I)[:5],
                       "botoes": [b for b in pg.eval_on_selector_all("button, a", "e=>e.map(x=>(x.innerText||'').trim())")
                                  if re.search(r"mais|pr[oó]xim|carregar|ver mais|^\d+$|›|»", b, re.I)][:30],
                       "links_pag": sorted({h for h in pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)")
                                            if re.search(r"pag|page", h, re.I)})[:15]}
    for q in ["?pagina=2", "?page=2", "/2", "?p=2"]:
        pg.goto(url + q, timeout=45000, wait_until="domcontentloaded"); pg.wait_for_timeout(6000)
        ps = props_de(pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)"), "auxiliadora")
        r.setdefault("tentativas_pag", {})[q] = {"props": len(ps), "ex": ps[:3]}
    r["api"] = api
    pg.remove_listener("response", on_resp)
    return r
bloco("auxiliadora", aux)

# 2) Sites JS que zeravam por causa do bug
def js_sites():
    r = {}
    for sid in ["creditoreal", "colnaghi", "private", "dacas"]:
        s = dict(SITES[sid]); s["listing_paths"] = s.get("listing_paths", ["/"])[:3]
        log = {}
        urls = render_js.coletar(s, log)
        ps = props_de(urls, sid)
        r[sid] = {"urls": len(urls), "props": len(ps), "ex_props": ps[:4], "log": log,
                  "ex_outros": sorted(u for u in urls if u not in ps)[:12]}
    return r
bloco("sites_js", js_sites)

# 3) Fichas que falham na leitura
def fichas():
    fal = json.load(open(os.path.join(ROOT, "data", "garimpo_falhas.json"), encoding="utf-8"))
    r = {}
    for dom in ["cpimoveis", "rial.com", "portolar", "guarida", "urban.imb", "novolar"]:
        us = [u for u in fal if dom in u][:3]
        r[dom] = []
        for u in us:
            info, html = get(u)
            enr, _ = m.enrich(u, S, cfg["bairros_alvo"])
            r[dom].append({"url": u, **info,
                           "enrich": {k: enr.get(k) for k in ("titulo", "preco", "bairro", "dorms", "endereco")},
                           "trecho": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:300]})
            time.sleep(1)
    return r
bloco("fichas", fichas)

# 4) Sites de listagem: quantos imóveis por página e até onde vai
def listagem():
    r = {}
    for sid in ["noblesse", "garcia", "luxton", "multiimob", "visualize", "oneluxo", "auxiliadora"]:
        s = SITES[sid]; base = s["base"]
        res = {}
        if sid == "auxiliadora":
            continue
        for pth in (s.get("listing_paths") or ["/"])[:2]:
            info, html = get(urljoin(base, pth))
            ls = links(html, base)
            res[pth] = {**info, "props": len(props_de(ls, sid)),
                        "pag": sorted(u for u in ls if re.search(r"pag|page|/\d+/?$", u, re.I))[:10],
                        "total": re.findall(r"([\d\.]+)\s*(?:im[oó]veis|resultados|encontrad)", html, re.I)[:4]}
        # tenta páginas altas para ver se a paginação segue
        p1 = (s.get("listing_paths") or [""])[0]
        if re.search(r"/1/$", p1):
            for n in (5, 10, 20, 40):
                info, html = get(urljoin(base, re.sub(r"/1/$", f"/{n}/", p1)))
                res[f"pagina_{n}"] = {"status": info.get("status"), "props": len(props_de(links(html, base), sid))}
        sm = {}
        for u in m.discover_sitemaps(base, S)[:4]:
            info, t = get(u)
            sm[u] = {"status": info.get("status"), "locs": len(re.findall(r"<loc>", t)),
                     "props": len(props_de(re.findall(r"<loc>\s*([^<\s]+)", t), sid))}
        res["sitemaps"] = sm
        r[sid] = res
    return r
bloco("listagem", listagem)
print("FIM")
