#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cruzamento do Radar com a base própria (Jetimob) e com o portal da RGI.

Fontes da "base conhecida" (todas opcionais — usa as que existirem):
  1. Feed XML do Jetimob     -> variável de ambiente JETIMOB_FEED_URL (GitHub Secret)
  2. Export manual CSV       -> data/meus_imoveis.csv
                                colunas: referencia,endereco,bairro,tipo,area,dormitorios,preco
  3. Site público da Boletto -> sitemap de bolettoimoveis.com.br
  4. Portal da RGI           -> sitemap de redegauchadeimoveis.com.br (toda a rede)

Cada imóvel do radar recebe:
  status: "livre" | "verificar" (possível match) | "captado"
  match_fonte / match_url / captado_em
O cruzamento reavalia TODOS os imóveis ainda não "captado" a cada execução —
assim você é avisado quando um imóvel livre passa a constar na base/rede.
"""
import csv, json, os, re, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CACHE_PATH = os.path.join(DATA_DIR, "base_cache.json")

TIPOS = ["apartamento", "cobertura", "casa", "terreno", "sala", "loja", "kitnet",
         "jk", "duplex", "garden", "studio", "predio", "prédio", "sobrado"]
AREA_PAT = re.compile(r"(\d{2,4})(?:[.,]\d+)?\s*m[²2]", re.I)
DORM_PAT = re.compile(r"(\d)\s*(?:dorm|quarto|suite|suíte)", re.I)
NUM_PAT = re.compile(r"[\d\.]{4,}(?:,\d{2})?")

def _num(preco_str):
    if not preco_str:
        return None
    m = NUM_PAT.search(str(preco_str))
    if not m:
        return None
    try:
        return float(m.group(0).replace(".", "").replace(",", "."))
    except ValueError:
        return None

def _tipo(text):
    t = (text or "").lower()
    for k in TIPOS:
        if k in t:
            return "predio" if k == "prédio" else k
    return None

def _area(text):
    m = AREA_PAT.search(text or "")
    return int(m.group(1)) if m else None

def _dorms(text):
    m = DORM_PAT.search(text or "")
    return int(m.group(1)) if m else None

def perfil_de_texto(texto, bairros_alvo, match_bairro):
    """Extrai perfil {bairro,tipo,area,dorms} de um texto/slug."""
    t = (texto or "").replace("-", " ")
    return {
        "bairro": match_bairro(t, bairros_alvo),
        "tipo": _tipo(t),
        "area": _area(t),
        "dorms": _dorms(t),
    }

# ------------------------------------------------------------------ fontes
def base_do_feed_xml(fetch, session, log):
    url = os.environ.get("JETIMOB_FEED_URL", "").strip()
    if not url:
        return []
    itens = []
    try:
        xml = fetch(url, session)
        # blocos de imóvel nos formatos comuns (VivaReal/ZAP/genérico)
        blocos = re.split(r"</(?:Listing|Imovel|imovel|item|anuncio)>", xml)
        for b in blocos:
            def tag(*names):
                for n in names:
                    m = re.search(r"<%s[^>]*>\s*(?:<!\[CDATA\[)?([^<\]]+)" % n, b, re.I)
                    if m:
                        return m.group(1).strip()
                return None
            bairro = tag("Neighborhood", "Bairro", "bairro")
            if not bairro and not tag("Title", "titulo", "TituloAnuncio"):
                continue
            itens.append({
                "fonte": "jetimob_feed",
                "url": tag("DetailViewUrl", "url", "Url") or url,
                "ref": tag("ListingID", "CodigoImovel", "referencia", "ref"),
                "bairro": bairro,
                "tipo": _tipo(tag("PropertyType", "TipoImovel", "tipo") or tag("Title", "titulo")),
                "area": _area((tag("LivingArea", "AreaUtil", "area") or "") + " m2") or
                        (int(float(tag("LivingArea", "AreaUtil", "area"))) if tag("LivingArea", "AreaUtil", "area") else None),
                "dorms": int(tag("Bedrooms", "QtdDormitorios", "dormitorios") or 0) or None,
                "preco": _num(tag("ListPrice", "PrecoVenda", "preco")),
                "endereco": tag("Address", "Endereco", "endereco"),
            })
        log["jetimob_feed"] = len(itens)
    except Exception as e:
        log["jetimob_feed_erro"] = str(e)[:150]
    return itens

def base_do_csv(log):
    path = os.path.join(DATA_DIR, "meus_imoveis.csv")
    if not os.path.exists(path):
        return []
    itens = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            g = lambda k: (row.get(k) or "").strip() or None
            itens.append({
                "fonte": "csv", "url": None, "ref": g("referencia"),
                "bairro": g("bairro"), "tipo": _tipo(g("tipo")),
                "area": int(float(g("area"))) if g("area") else None,
                "dorms": int(g("dormitorios")) if g("dormitorios") else None,
                "preco": _num(g("preco")), "endereco": g("endereco"),
            })
    log["csv"] = len(itens)
    return itens

def base_de_sitemap(nome, base_url, fetch, session, collect_urls, enrich, cache,
                    bairros_alvo, match_bairro, cap, log):
    """Coleta URLs de imóveis de um site 'nosso' (site próprio / portal RGI).
    Perfil vem do slug; até `cap` páginas ainda não cacheadas são enriquecidas por execução."""
    itens = []
    try:
        urls = collect_urls({"base": base_url, "id": nome}, session, {})
        urls = [u for u in urls if re.search(r"imove|imovel", u, re.I) and re.search(r"\d", u)]
        log[nome + "_urls"] = len(urls)
        fetched = 0
        for u in urls:
            entry = cache.get(u)
            if entry is None:
                entry = perfil_de_texto(u.split("/")[-1] or u.split("/")[-2], bairros_alvo, match_bairro)
                entry["fonte"] = nome
                # slug insuficiente? busca a página (limitado por execução)
                if (entry["bairro"] is None or entry["area"] is None) and fetched < cap:
                    info, _ = enrich(u, session, bairros_alvo)
                    fetched += 1
                    texto = " ".join(x for x in (info.get("titulo"), info.get("descricao")) if x)
                    entry["bairro"] = entry["bairro"] or info.get("bairro")
                    entry["tipo"] = entry["tipo"] or _tipo(texto)
                    entry["area"] = entry["area"] or _area(texto)
                    entry["dorms"] = entry["dorms"] or _dorms(texto)
                    entry["preco"] = _num(info.get("preco"))
                    time.sleep(0.6)
                cache[u] = entry
            item = dict(entry)
            item["url"] = u
            itens.append(item)
        log[nome] = len(itens)
    except Exception as e:
        log[nome + "_erro"] = str(e)[:150]
    return itens

# ------------------------------------------------------------------ matching
def score_match(radar, base):
    """radar/base: perfis com bairro,tipo,area,dorms,preco. Retorna pontuação."""
    s = 0
    if radar.get("bairro") and base.get("bairro"):
        if radar["bairro"].lower() != str(base["bairro"]).lower():
            return 0          # bairros conhecidos e diferentes: descarta
        s += 2
    if radar.get("tipo") and base.get("tipo"):
        if radar["tipo"] != base["tipo"]:
            return 0
        s += 1
    ra, ba = radar.get("area"), base.get("area")
    if ra and ba and abs(ra - ba) <= max(2, 0.05 * ba):
        s += 3
    rd, bd = radar.get("dorms"), base.get("dorms")
    if rd and bd and rd == bd:
        s += 1
    rp, bp = radar.get("preco"), base.get("preco")
    if rp and bp and abs(rp - bp) <= 0.07 * bp:
        s += 2
    return s

def cruzar(listings, base_itens, bairros_alvo, match_bairro, today):
    """Atualiza status dos imóveis do radar contra a base conhecida."""
    mudancas = 0
    for l in listings:
        if l.get("status") == "captado":
            continue
        texto = " ".join(x for x in (l.get("titulo"), l.get("descricao"),
                                     l.get("url", "").split("/")[-1].replace("-", " ")) if x)
        perfil = {
            "bairro": l.get("bairro"),
            "tipo": _tipo(texto),
            "area": _area(texto),
            "dorms": _dorms(texto),
            "preco": _num(l.get("preco")),
        }
        melhor, melhor_s = None, 0
        for b in base_itens:
            s = score_match(perfil, b)
            if s > melhor_s:
                melhor, melhor_s = b, s
        novo = "livre"
        if melhor_s >= 7:
            novo = "captado"
        elif melhor_s >= 5:
            novo = "verificar"
        if novo != l.get("status", "livre"):
            l["status"] = novo
            l["match_fonte"] = melhor["fonte"] if melhor else None
            l["match_url"] = melhor.get("url") if melhor else None
            l["match_ref"] = melhor.get("ref") if melhor else None
            if novo == "captado":
                l["captado_em"] = today
            mudancas += 1
        elif "status" not in l:
            l["status"] = "livre"
    return mudancas

def executar(cfg, listings, session, fetch, collect_urls, enrich, match_bairro, today):
    cz = cfg.get("cruzamento", {})
    bairros_alvo = cfg["bairros_alvo"]
    log = {}
    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH, encoding="utf-8"))
    base = []
    base += base_do_feed_xml(fetch, session, log)
    base += base_do_csv(log)
    cap = cz.get("max_enriquecimento_por_execucao", 150)
    if cz.get("site_proprio"):
        base += base_de_sitemap("site_proprio", cz["site_proprio"], fetch, session,
                                collect_urls, enrich, cache, bairros_alvo, match_bairro, cap, log)
    if cz.get("portal_rgi"):
        base += base_de_sitemap("portal_rgi", cz["portal_rgi"], fetch, session,
                                collect_urls, enrich, cache, bairros_alvo, match_bairro, cap, log)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    log["base_total"] = len(base)
    log["mudancas_status"] = cruzar(listings, base, bairros_alvo, match_bairro, today)
    return log
