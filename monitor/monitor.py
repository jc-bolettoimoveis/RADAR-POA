#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Radar de Captação — Boletto Imóveis
Monitora sites de imobiliárias fora da RGI e detecta imóveis novos (venda e, quando
ativado, locação) nos bairros-alvo. Estado em data/, painel gerado por site/build_site.py.

Estratégia por site:
  1. Descobre sitemap (robots.txt -> sitemap.xml / sitemap_index.xml).
  2. Coleta URLs que parecem páginas de imóvel individual.
  3. Compara com data/known_urls.json. Primeira execução = linha de base (não alerta).
  4. URLs novas são enriquecidas (título, foto, preço, bairro via OpenGraph/HTML)
     e gravadas em data/listings.json.
"""
import json, os, re, sys, time, gzip, io
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "config", "sites.json")
DATA_DIR = os.path.join(ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
TIMEOUT = 25
DELAY_BETWEEN_REQ = 1.2      # educação com os servidores
MAX_SUBSITEMAPS = 40
MAX_URLS_PER_SITE = 30000
MAX_NEW_ENRICH = 120          # máx. de páginas de detalhe buscadas por site por execução

LOC_PAT   = re.compile(r"alug|loca[cç][aã]o|aluguel|/rent", re.I)
VENDA_PAT = re.compile(r"vend|compr|/sale|a-venda|à-venda", re.I)
# URL que parece ser página de UM imóvel (não listagem): contém termo típico + código numérico
PROP_PAT  = re.compile(
    r"(im[oó]ve(l|is)|apartamento|casa|cobertura|terreno|sala|loja|kitnet|jk|"
    r"predio|pr[eé]dio|duplex|garden|studio|empreendimento|codigo|ref)", re.I)
NUM_PAT   = re.compile(r"\d{2,}")
EXCLUDE_PAT = re.compile(
    r"(blog|noticia|artigo|sobre|contato|equipe|politica|privacidade|trabalhe|"
    r"login|admin|wp-|/tag/|/category/|/autor|/busca/|/pesquisa|agenda_visita|"
    r"\.(jpg|jpeg|png|gif|webp|pdf|css|js)($|\?))", re.I)
PRICE_PAT = re.compile(r"R\$\s?[\d\.]{4,}(?:,\d{2})?")

FICHA_CAMPOS = ("dorms", "suites", "vagas", "banheiros", "area", "area_total",
                "preco_venda", "preco_locacao", "condominio", "iptu", "codigo",
                "endereco", "caracteristicas", "completude",
                "preco_locacao_fmt", "condominio_fmt", "iptu_fmt",
                "latitude", "longitude", "empreendimento", "tipo_imovel",
                "numero", "endereco_nivel", "prioridade")

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

def fetch(url, session, binary=False):
    r = session.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    if binary:
        return r.content
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text

# ---------------------------------------------------------------- sitemap
def discover_sitemaps(base, session):
    found = []
    try:
        robots = fetch(urljoin(base, "/robots.txt"), session)
        found += re.findall(r"(?im)^sitemap:\s*(\S+)", robots)
    except Exception:
        pass
    for guess in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/sitemap/sitemap.xml"):
        u = urljoin(base, guess)
        if u not in found:
            found.append(u)
    return found

def parse_sitemap(content_bytes_or_text):
    text = content_bytes_or_text
    if isinstance(text, bytes):
        if text[:2] == b"\x1f\x8b":
            text = gzip.GzipFile(fileobj=io.BytesIO(text)).read()
        text = text.decode("utf-8", errors="replace")
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
    locs = [u.replace("&amp;", "&") for u in locs]
    is_index = "<sitemapindex" in text
    return locs, is_index

def collect_site_urls(site, session, log):
    """Retorna set de URLs candidatas a página de imóvel."""
    base = site["base"]
    urls = set()
    if site.get("ignorar_sitemap"):
        site = dict(site)          # força o fluxo de listagem
        _sm = discover_sitemaps
    if site.get("render"):
        try:
            import render_js
            urls = render_js.coletar(site, log)
            log["urls_coletadas"] = len(urls)
            return urls
        except Exception as e:
            log["render_erro"] = str(e)[:150]
            # se a renderização falhar, cai no fluxo normal abaixo
    used_sitemap = False
    for sm in ([] if site.get("ignorar_sitemap") else discover_sitemaps(base, session)):
        try:
            content = fetch(sm, session, binary=True)
            locs, is_index = parse_sitemap(content)
            if not locs:
                continue
            used_sitemap = True
            if is_index:
                # prioriza sub-sitemaps que aparentam conter imóveis
                locs.sort(key=lambda u: 0 if re.search(r"im[oó]?ve|prop|post|product", u, re.I) else 1)
                for sub in locs[:MAX_SUBSITEMAPS]:
                    try:
                        c2 = fetch(sub, session, binary=True)
                        l2, _ = parse_sitemap(c2)
                        urls.update(l2)
                        time.sleep(0.4)
                        if len(urls) > MAX_URLS_PER_SITE:
                            break
                    except Exception:
                        continue
            else:
                urls.update(locs)
            if urls:
                break   # um sitemap válido basta
        except Exception:
            continue
    if not urls:
        # fallback: varre a home + páginas de listagem óbvias, extrai links
        log["metodo"] = "listagem"
        paths = site.get("listing_paths") or ("/", "/venda", "/imoveis", "/comprar", "/imoveis/venda", "/busca")
        for path in paths:
            try:
                html = fetch(urljoin(base, path), session)
                for href in re.findall(r'href=["\']([^"\'#]+)', html):
                    full = urljoin(base, href)
                    if urlparse(full).netloc == urlparse(base).netloc:
                        urls.add(full.split("?")[0])
                time.sleep(DELAY_BETWEEN_REQ)
            except Exception:
                continue
    else:
        log["metodo"] = "sitemap"
    if site.get("tambem_listagem") or (0 < len(urls) < 10):
        # sitemap existe mas é raso: complementa com as páginas de listagem
        log["metodo"] = "sitemap+listagem"
        paths = site.get("listing_paths") or ("/", "/venda", "/imoveis", "/comprar", "/imoveis/venda", "/busca")
        for path in paths:
            try:
                html = fetch(urljoin(base, path), session)
                for href in re.findall(r'href=["\']([^"\'#]+)', html):
                    full = urljoin(base, href)
                    if urlparse(full).netloc == urlparse(base).netloc:
                        urls.add(full)
                time.sleep(DELAY_BETWEEN_REQ)
            except Exception:
                continue
    # -------- segunda onda: segue links de paginação encontrados --------
    PAG_PAT = re.compile(r"([?&](?:pagina|pag|page|p)=\d+|/pagina/\d+/?$|/page/\d+/?$)", re.I)
    LISTA_PAT = re.compile(r"busca|venda|comprar|alugar|imoveis|locacao", re.I)
    max_pag = site.get("paginas_extra", 12)
    candidatos = sorted(u for u in urls
                        if PAG_PAT.search(u) and LISTA_PAT.search(u)
                        and not is_property_url(u, site))[:max_pag]
    for pu in candidatos:
        try:
            if site.get("render"):
                import render_js
                html = render_js.get_html(pu)
            else:
                html = fetch(pu, session)
            for href in re.findall(r'href=["\']([^"\'#]+)', html):
                full = urljoin(base, href)
                if urlparse(full).netloc == urlparse(base).netloc:
                    urls.add(full)
            time.sleep(DELAY_BETWEEN_REQ)
        except Exception:
            continue
    if candidatos:
        log["paginas_extra_visitadas"] = len(candidatos)
    log["urls_coletadas"] = len(urls)
    return urls

# ---------------------------------------------------------------- classificação
def is_property_url(url, site):
    pat = site.get("url_pattern")
    path = urlparse(url).path
    if EXCLUDE_PAT.search(url):
        return False
    if pat:
        return re.search(pat, url, re.I) is not None
    return bool(PROP_PAT.search(path) and NUM_PAT.search(path)) or bool(
        re.search(r"/(imovel|imoveis|property)/[^/]+", path, re.I) and NUM_PAT.search(path))

def url_tipo(url):
    if LOC_PAT.search(url):
        return "locacao"
    if VENDA_PAT.search(url):
        return "venda"
    return "indefinido"

def match_bairro(text, bairros_alvo):
    t = text.lower()
    for canonico, variantes in bairros_alvo.items():
        for v in variantes:
            if v in t:
                return canonico
    return None

# ---------------------------------------------------------------- enriquecimento
def enrich(url, session, bairros_alvo, render=False):
    info = {"titulo": None, "foto": None, "preco": None, "bairro": None, "descricao": None}
    html = None
    if render:
        try:
            import render_js
            html = render_js.get_html(url)
        except Exception:
            html = None
    if html is None:
        try:
            html = fetch(url, session)
        except Exception:
            return info, None
    def meta(prop):
        m = re.search(
            r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)' % re.escape(prop),
            html, re.I) or re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(prop),
            html, re.I)
        return m.group(1).strip() if m else None
    info["titulo"] = meta("og:title") or (re.search(r"<title[^>]*>([^<]+)", html, re.I) or [None, None])[1]
    if info["titulo"]:
        info["titulo"] = info["titulo"].strip()[:160]
    info["foto"] = meta("og:image")   # pode ser logo — corrigido após o extrator
    info["descricao"] = (meta("og:description") or meta("description") or "")[:300] or None
    m = PRICE_PAT.search(html)
    if m:
        info["preco"] = m.group(0)
    try:
        from extrator import extrair
        det = extrair(html, url)
        for k in FICHA_CAMPOS:
            info[k] = det.get(k)
        if det.get("preco_venda_fmt"):
            info["preco"] = det["preco_venda_fmt"]
        from extrator import FOTO_RUIM
        if info.get("foto") and FOTO_RUIM.search(info["foto"]):
            info["foto"] = None
        info["foto"] = info["foto"] or det.get("foto_boa")
    except Exception:
        pass
    texto_busca = " ".join(x for x in (url, info["titulo"], info["descricao"]) if x)
    info["bairro"] = match_bairro(texto_busca, bairros_alvo) or match_bairro(html[:60000], bairros_alvo)
    # tipo pelo conteúdo, caso a URL não diga
    tipo_html = None
    low = (info["titulo"] or "").lower() + " " + (info["descricao"] or "").lower()
    if LOC_PAT.search(low):
        tipo_html = "locacao"
    elif VENDA_PAT.search(low):
        tipo_html = "venda"
    return info, tipo_html

# ---------------------------------------------------------------- principal
def main():
    cfg = load_json(CFG_PATH, None)
    if not cfg:
        print("config/sites.json não encontrado"); sys.exit(1)
    monitorar = cfg["monitorar"]
    bairros_alvo = cfg["bairros_alvo"]
    somente_alvo = cfg.get("somente_bairros_alvo", True)

    known = load_json(os.path.join(DATA_DIR, "known_urls.json"), {})
    listings = load_json(os.path.join(DATA_DIR, "listings.json"), [])
    listing_urls = {l["url"] for l in listings}
    runlog = {"executado_em": now_iso(), "sites": {}}
    novos_da_execucao, removidos_agora, quedas_agora = [], [], []

    session = requests.Session()
    render_ids = {s["id"] for s in cfg["sites"] if s.get("render") and s.get("enabled")}

    for site in cfg["sites"]:
        if not site.get("enabled"):
            continue
        sid, nome = site["id"], site["nome"]
        log = {"nome": nome, "status": "ok", "novos": 0, "erro": None}
        print(f"== {nome} ({site['base']})")
        try:
            urls = collect_site_urls(site, session, log)
            props = {u for u in urls if is_property_url(u, site)}
            log["urls_imovel"] = len(props)
            # autodiagnóstico: guarda exemplos p/ calibrar filtros
            if props:
                log["exemplo_imovel"] = sorted(props)[:3]
            elif urls:
                log["exemplos_urls"] = [u for u in sorted(urls)
                                        if not re.search(r"\.(css|js|png|jpe?g|webp|xml|pdf)([?#]|$)", u)][:8]

            prev = set(known.get(sid, []))
            baseline = sid not in known
            if not baseline and len(props - prev) > 150:
                baseline = True   # site recalibrado: refaz linha de base em vez de alertar em massa
                log["obs"] = "recalibrado: nova linha de base"
            new_urls = sorted(props - prev)
            known[sid] = sorted(props | prev)   # nunca esquece URL já vista

            if baseline:
                log["status"] = "linha_de_base"
                log["estoque_inicial"] = len(props)
                print(f"   linha de base: {len(props)} imóveis registrados (sem alertas)")
            else:
                enriched = 0
                for u in new_urls:
                    if u in listing_urls:
                        continue
                    tipo = url_tipo(u)
                    info, tipo_html = ({}, None)
                    if enriched < MAX_NEW_ENRICH:
                        info, tipo_html = enrich(u, session, bairros_alvo, render=sid in render_ids)
                        enriched += 1
                        time.sleep(DELAY_BETWEEN_REQ)
                    if tipo == "indefinido" and tipo_html:
                        tipo = tipo_html
                    # filtra pelo modo monitorado
                    if tipo == "locacao" and not monitorar.get("locacao"):
                        continue
                    if tipo == "venda" and not monitorar.get("venda"):
                        continue
                    bairro = info.get("bairro")
                    if somente_alvo and bairro is None and info.get("titulo"):
                        # página lida e nenhum bairro-alvo citado -> fora da região
                        continue
                    listings.append({
                        "url": u, "site_id": sid, "imobiliaria": nome,
                        "tipo": tipo, "bairro": bairro,
                        "titulo": info.get("titulo"), "foto": info.get("foto"),
                        "preco": info.get("preco"), "descricao": info.get("descricao"),
                        "detectado_em": today(), "ultima_verificacao": today(),
                        **{k: info.get(k) for k in FICHA_CAMPOS},
                    })
                    listing_urls.add(u)
                    novos_da_execucao.append(listings[-1])
                    log["novos"] += 1
                print(f"   {len(new_urls)} URLs novas, {log['novos']} imóveis registrados")
                # anúncios que sumiram (só se a coleta do site foi confiável nesta rodada)
                prev_count = sum(1 for l in listings if l.get("site_id") == sid and not l.get("removido_em"))
                coleta_ok = len(props) >= max(3, prev_count * 0.5)   # coletou ao menos metade do conhecido
                faltas_necessarias = 3 if site.get("render") else 2  # sites JS: mais tolerância
                for l in (listings if coleta_ok else []):
                    if l.get("site_id") != sid or l.get("removido_em"):
                        continue
                    if l["url"] not in props:
                        l["faltas"] = l.get("faltas", 0) + 1
                        if l["faltas"] >= faltas_necessarias:
                            l["removido_em"] = today()
                            removidos_agora.append(l)
                    else:
                        l["faltas"] = 0
                if removidos_agora:
                    log["removidos"] = sum(1 for l in removidos_agora if l.get("site_id") == sid)
        except Exception as e:
            log["status"] = "erro"
            log["erro"] = str(e)[:200]
            print(f"   ERRO: {e}")
        runlog["sites"][sid] = log
        time.sleep(DELAY_BETWEEN_REQ)

    # ---------------- revisita: atualiza preço dos anúncios ativos (detecta quedas) -----
    REVISITA_CAP = 120
    def _preco_num(p):
        m = re.search(r"[\d\.]{4,}(?:,\d{2})?", p or "")
        return float(m.group(0).replace(".", "").replace(",", ".")) if m else None
    ativos = [l for l in listings if not l.get("removido_em") and l.get("status") != "captado"]
    ativos.sort(key=lambda l: l.get("ultima_verificacao") or "")
    for l in ativos[:REVISITA_CAP]:
        info, _ = enrich(l["url"], session, bairros_alvo,
                         render=l.get("site_id") in render_ids)
        l["ultima_verificacao"] = today()
        novo_p = info.get("preco")
        antigo_n, novo_n = _preco_num(l.get("preco")), _preco_num(novo_p)
        if antigo_n and novo_n and novo_n < antigo_n * 0.97:
            l["queda"] = {"de": l.get("preco"), "para": novo_p, "em": today()}
            l["preco"] = novo_p
            quedas_agora.append(l)
        elif novo_p and not l.get("preco"):
            l["preco"] = novo_p
        if info.get("titulo") and not l.get("titulo"):
            l["titulo"] = info["titulo"]
            l["foto"] = l.get("foto") or info.get("foto")
        for k in FICHA_CAMPOS:
            if info.get(k) and not l.get(k):
                l[k] = info[k]
        if (info.get("completude") or 0) > (l.get("completude") or 0):
            l["completude"] = info["completude"]
        time.sleep(0.8)
    if quedas_agora:
        print(f"Revisita: {len(quedas_agora)} queda(s) de preço detectada(s)")

    # ---------------- faxina: remove cards que não são página de imóvel ----------------
    scfg_val = {s["id"]: s for s in cfg["sites"]}
    antes_val = len(listings)
    listings[:] = [l for l in listings
                   if is_property_url(l["url"], scfg_val.get(l.get("site_id"), {}))]
    if len(listings) != antes_val:
        listing_urls = {l["url"] for l in listings}
        print(f"Faxina: {antes_val - len(listings)} cards inválidos removidos (ex.: páginas de busca)")

    # ---------------- cruzamento com base própria (Jetimob) e portal RGI ----------------
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import cruzamento
        czlog = cruzamento.executar(cfg, listings, session, fetch,
                                    collect_site_urls, enrich, match_bairro, today())
        runlog["cruzamento"] = czlog
        print("Cruzamento:", json.dumps(czlog, ensure_ascii=False))
    except Exception as e:
        runlog["cruzamento"] = {"erro": str(e)[:200]}
        print("Cruzamento falhou:", e)

    # ---------------- alertas WhatsApp -------------------------------------------------
    novos_livres = [l for l in novos_da_execucao if l.get("status", "livre") == "livre"]
    novos_livres.sort(key=lambda l: l.get("prioridade") or 9)
    try:
        import alertas
        runlog["alertas"] = alertas.enviar(novos_livres, removidos_agora, quedas_agora,
                                           os.environ.get("PAINEL_URL"))
        print("Alertas:", json.dumps(runlog["alertas"], ensure_ascii=False))
    except Exception as e:
        runlog["alertas"] = {"erro": str(e)[:200]}

    save_json(os.path.join(DATA_DIR, "known_urls.json"), known)
    save_json(os.path.join(DATA_DIR, "listings.json"), listings)
    save_json(os.path.join(DATA_DIR, "runlog.json"), runlog)
    try:
        import sheets_sync
        runlog["sheets"] = sheets_sync.enviar(listings)
        print("Google Sheets:", json.dumps(runlog["sheets"], ensure_ascii=False))
    except Exception as e:
        runlog["sheets"] = {"erro": str(e)[:150]}

    total_novos = sum(s["novos"] for s in runlog["sites"].values())
    print(f"\nConcluído. {total_novos} imóveis novos nesta execução.")

if __name__ == "__main__":
    main()
