#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sondagem temporária (rodada 2). Grava diag/resultado2.json."""
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

def get(url, headers=None):
    try:
        r = S.get(url, headers=headers or m.HEADERS, timeout=25)
        return r.status_code, r.text
    except Exception as e:
        return str(e)[:150], ""

def props(urls, sid):
    return sorted({u for u in urls if m.is_property_url(u, SITES[sid])})

def bloco(nome, fn):
    try:
        OUT[nome] = fn()
    except Exception:
        OUT[nome] = {"excecao": traceback.format_exc()[-800:]}
    json.dump(OUT, open(os.path.join(ROOT, "diag", "resultado2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("ok", nome, flush=True)

def aux():
    st, idx = get("https://www.auxiliadorapredial.com.br/images/cms/sitemaps/sitemap-ap.xml")
    subs = re.findall(r"<loc>\s*([^<\s]+)", idx)
    poa = [u for u in subs if "porto-alegre" in u]
    r = {"total_subs": len(subs), "poa": poa, "tipos": sorted({u.split("/")[-1].split("+")[0] for u in subs})}
    tot = set()
    for u in poa:
        st, t = get(u)
        locs = re.findall(r"<loc>\s*([^<\s]+)", t)
        tot.update(locs)
        r.setdefault("por_sub", {})[u.split("/")[-1]] = {"status": st, "locs": len(locs), "ex": locs[:2]}
        time.sleep(0.3)
    r["total_poa"] = len(tot)
    r["props_poa"] = len(props(tot, "auxiliadora"))
    r["nao_props_ex"] = [u for u in sorted(tot) if not m.is_property_url(u, SITES["auxiliadora"])][:10]
    # ficha sem navegador: dá para ler?
    ex = props(tot, "auxiliadora")[:2]
    for u in ex:
        st, html = get(u)
        info, _ = m.enrich(u, S, cfg["bairros_alvo"])
        r.setdefault("ficha_sem_render", []).append({"url": u, "status": st, "len": len(html),
            "info": {k: info.get(k) for k in ("titulo", "preco", "bairro", "dorms", "area", "endereco")}})
    return r
bloco("auxiliadora", aux)

def cp():
    fal = json.load(open(os.path.join(ROOT, "data", "garimpo_falhas.json"), encoding="utf-8"))
    us = [u for u in fal if "cpimoveis" in u][:2]
    r = []
    for u in us:
        variantes = {"dupla_barra": u, "barra_simples": re.sub(r"(?<!:)//+", "/", u)}
        for nome, uu in variantes.items():
            for hn, h in {"padrao": m.HEADERS,
                          "navegador": {**m.HEADERS, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                                        "Accept-Language": "pt-BR,pt;q=0.9"}}.items():
                st, t = get(uu, h)
                r.append({"var": nome, "hdr": hn, "status": st, "len": len(t),
                          "titulo": (re.search(r"<title[^>]*>([^<]{0,100})", t) or [None, None])[1]})
        try:
            html = render_js.get_html(u)
            info = {}
            from extrator import extrair
            d = extrair(html, u)
            r.append({"render_len": len(html), "titulo": (re.search(r"<title[^>]*>([^<]{0,100})", html) or [None, None])[1],
                      "extr": {k: d.get(k) for k in ("preco_venda_fmt", "dorms", "area", "endereco", "bairro")}})
        except Exception as e:
            r.append({"render_erro": str(e)[:200]})
    st, home = get("https://www.cpimoveis.com.br/")
    r.append({"home_status": st, "home_len": len(home)})
    return {"testes": r}
bloco("cpimoveis", cp)

def rial():
    r = []
    for u in ["https://rial.com.br/detalhes_loc.php?imovel=2303&Google=Apartamento+HIGIENOPOLIS+",
              "https://portolar.com.br/detalhes_vd.php?imovel=1095&Google=Rio%20Branco%20+Apartamento"]:
        html = render_js.get_html(u)
        from extrator import extrair
        d = extrair(html, u)
        txt = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html, flags=re.S))
        r.append({"url": u, "len": len(html), "titulo": (re.search(r"<title[^>]*>([^<]{0,100})", html) or [None, None])[1],
                  "extr": {k: d.get(k) for k in ("preco_venda_fmt", "dorms", "area", "endereco")},
                  "iframes": re.findall(r"<iframe[^>]+src=[\"']([^\"']+)", html)[:5], "texto": txt[:500]})
    return {"r": r}
bloco("rial_portolar", rial)

def dacas():
    pg = render_js._pagina()
    pg.goto("https://www.dacas.com.br/", timeout=45000, wait_until="domcontentloaded"); pg.wait_for_timeout(6000)
    hs = pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)")
    st, robots = get("https://www.dacas.com.br/robots.txt")
    return {"titulo": pg.title(), "final": pg.url, "links": sorted(set(hs))[:40], "robots": robots[:300]}
bloco("dacas", dacas)

def paginacao():
    r = {}
    for sid, tpl in {"noblesse": "/busca/comprar/cidade/porto-alegre/{n}/",
                     "garcia": "/busca/comprar/cidade/porto-alegre/{n}/",
                     "luxton": "/busca/comprar/site/poa/cidade/porto-alegre/{n}/",
                     "multiimob": "/busca/comprar/cidade/Porto Alegre/{n}/"}.items():
        base = SITES[sid]["base"]; vistos = set(); serie = []
        for n in (0, 1, 2, 3, 30, 60, 63, 64, 65, 72, 73, 107, 108, 120, 200):
            st, t = get(urljoin(base, tpl.format(n=n)))
            ls = {urljoin(base, h) for h in re.findall(r'href=["\']([^"\'#]+)', t)}
            ps = set(props(ls, sid))
            serie.append((n, st, len(ps), len(ps - vistos)))
            vistos |= ps
            time.sleep(0.4)
        r[sid] = serie
    return r
bloco("paginacao", paginacao)
print("FIM")
