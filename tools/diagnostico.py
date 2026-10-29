#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sondagem temporária: onde cada site guarda endereço/condomínio/mapa na página COMPLETA do anúncio."""
import json, os, re, sys, time, random, traceback
from urllib.parse import unquote
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "monitor"))
import monitor as m
import render_js
from extrator import extrair

cfg = json.load(open(os.path.join(ROOT, "config", "sites.json"), encoding="utf-8"))
L = m.load_listings()
OUT = {}
random.seed(7)
CHAVES = re.compile(r'"(logradouro|endereco|endere[çc]o|address|street\w*|rua|numero|number|'
                    r'lat|latitude|lng|lon|longitude|condominio|edificio|empreendimento|cep)"\s*:\s*("[^"]{1,90}"|-?\d[\d\.]*)', re.I)

def salvar():
    json.dump(OUT, open(os.path.join(ROOT, "diag", "fontes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def sondar(url):
    pg = render_js._pagina()
    rede = []
    def on_resp(resp):
        try:
            u = resp.url
            if re.search(r"maps\.googleapis|google\.com/maps|staticmap|geocod|nominatim|mapbox|openstreetmap|leaflet", u, re.I):
                rede.append(("mapa", u[:400]))
            ct = resp.headers.get("content-type", "")
            if "json" in ct and len(rede) < 60:
                body = resp.text()[:200000]
                hits = CHAVES.findall(body)
                if hits:
                    rede.append(("json", u[:200], hits[:12]))
        except Exception:
            pass
    pg.on("response", on_resp)
    r = {"url": url}
    try:
        html = render_js.get_html(url)
        d = extrair(html, url)
        r["extrator"] = {k: d.get(k) for k in ("endereco", "numero", "empreendimento", "latitude", "longitude", "tipo_imovel")}
        txt = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html, flags=re.S))
        r["titulo"] = pg.title()[:150]
        r["trechos"] = [txt[max(0, mm.start() - 120): mm.end() + 160]
                        for mm in re.finditer(r"localiza|endere[çc]o|mapa|condom[íi]nio|edif[íi]cio|residencial", txt, re.I)][:6]
        r["iframes"] = re.findall(r"<iframe[^>]+src=[\"']([^\"']+)", html, re.I)[:6]
        r["links_mapa"] = sorted(set(re.findall(r"https?://[^\"'\s<>]*(?:maps|goo\.gl|waze)[^\"'\s<>]*", html, re.I)))[:8]
        r["chaves_html"] = CHAVES.findall(html)[:15]
        # clica em qualquer botão/link de mapa
        cliques = []
        for sel in ["text=/ver mapa/i", "text=/mapa/i", "text=/localiza[çc][ãa]o/i", "text=/como chegar/i"]:
            try:
                el = pg.locator(sel).first
                if el.count() and el.is_visible():
                    el.click(timeout=4000)
                    pg.wait_for_timeout(3500)
                    h2 = pg.content()
                    cliques.append({"sel": sel,
                                    "iframes": re.findall(r"<iframe[^>]+src=[\"']([^\"']+)", h2, re.I)[:6],
                                    "links_mapa": sorted(set(re.findall(r"https?://[^\"'\s<>]*(?:maps|goo\.gl|waze)[^\"'\s<>]*", h2, re.I)))[:8],
                                    "ll": extrair(h2, url).get("latitude"),
                                    "novo_texto": [t for t in re.findall(r"(?:Rua|Av\.?|Avenida|Travessa|Alameda|R\.)\s+[A-ZÀ-Ü][^<>\n]{3,60}", h2)][:6]})
                    break
            except Exception as e:
                cliques.append({"sel": sel, "erro": str(e)[:100]})
        r["cliques"] = cliques
    except Exception:
        r["erro"] = traceback.format_exc()[-300:]
    r["rede"] = rede[:25]
    pg.remove_listener("response", on_resp)
    return r

os.makedirs(os.path.join(ROOT, "diag"), exist_ok=True)
ordem = ["urban", "bridge", "lyon", "private", "auxiliadora", "guarida", "novolar", "sperinde", "foxter", "jsimas",
         "veronez", "don", "casaporto", "garcia", "noblesse", "morano", "terracini", "oneluxo", "albert", "cpimoveis",
         "creditoreal", "colnaghi", "multiimob", "condotta", "rial", "luxton", "visualize", "verabernardes", "zonanorte", "portolar"]
for sid in ordem:
    cand = [l for l in L if l["site_id"] == sid and not l.get("removido_em")]
    sem = [l for l in cand if not l.get("numero")] or cand
    random.shuffle(sem)
    OUT[sid] = []
    for l in sem[:2]:
        t = time.time()
        r = sondar(l["url"])
        r["guardado"] = {k: l.get(k) for k in ("endereco", "numero", "empreendimento", "endereco_nivel", "tipo_imovel")}
        r["seg"] = round(time.time() - t, 1)
        OUT[sid].append(r)
        salvar()
    print("ok", sid, flush=True)
print("FIM", flush=True)
