#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Descobre o endereço (rua + número) de anúncios que só citam o PRÉDIO/CONDOMÍNIO.

1. Dicionário interno: aprende o endereço de cada prédio com os anúncios que o
   revelam (qualquer imobiliária) e aplica nos que escondem. Chave = nome + bairro.
2. Google Places (Text Search), se houver a chave GOOGLE_MAPS_API_KEY: busca
   "Condomínio X, Bairro, Porto Alegre" e confere se o nome do resultado bate.
   Respeita uma cota mensal (GOOGLE_COTA_MENSAL, padrão 4500 consultas).
3. Sem chave do Google: OpenStreetMap/Nominatim (gratuito, 1 consulta/s).
Resultados ficam em data/geocache.json para não repetir consultas.
"""
import json, os, re, time
from datetime import datetime, timezone
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CACHE = os.path.join(DATA_DIR, "geocache.json")
NOMINATIM_CAP = int(os.environ.get("NOMINATIM_CAP") or "100")      # consultas por execução
GOOGLE_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
GOOGLE_COTA_MENSAL = int(os.environ.get("GOOGLE_COTA_MENSAL") or "4500")
GOOGLE_CAP_EXEC = int(os.environ.get("GOOGLE_CAP_EXEC") or "600")
GOOGLE_VALIDADE_DIAS = 30
UA = {"User-Agent": "RadarCaptacao/1.0 (uso interno; contato via github)"}
POA = {"low": {"latitude": -30.27, "longitude": -51.31}, "high": {"latitude": -29.93, "longitude": -51.05}}
STOP = {"condominio", "edificio", "residencial", "ed", "de", "da", "do", "das", "dos", "e", "the",
        "torre", "bloco", "park", "home", "club", "residence", "porto", "alegre"}

def _sem_acento(s):
    return str(s or "").lower().translate(str.maketrans("áàâãéêëíìóòôõúùüç", "aaaaeeeiiooooouuc"))

def _norm(nome):
    if not nome:
        return None
    n = _sem_acento(nome)
    n = re.sub(r"^(condominio|edificio|residencial|ed\.?)\s+", "", n.strip())
    return re.sub(r"\s+", " ", n).strip() or None

def _tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", _sem_acento(s)) if t not in STOP and len(t) > 1}

def _parecido(nome_predio, nome_resultado):
    a, b = _tokens(nome_predio), _tokens(nome_resultado)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)

def _dentro_poa(la, lo):
    return -30.30 < la < -29.85 and -51.35 < lo < -51.03

def _hoje():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _google(emp_original, bairro, cache):
    mes = _hoje()[:7]
    uso = cache.setdefault("_uso_google", {})
    if uso.get(mes, 0) >= GOOGLE_COTA_MENSAL:
        return "cota"
    uso[mes] = uso.get(mes, 0) + 1
    q = ", ".join(x for x in (emp_original, bairro, "Porto Alegre - RS") if x)
    r = requests.post("https://places.googleapis.com/v1/places:searchText",
                      headers={"X-Goog-Api-Key": GOOGLE_KEY,
                               "X-Goog-FieldMask": "places.displayName,places.formattedAddress,"
                                                   "places.location,places.addressComponents,places.types"},
                      json={"textQuery": q, "languageCode": "pt-BR", "regionCode": "BR", "pageSize": 3,
                            "locationRestriction": {"rectangle": POA}}, timeout=20)
    r.raise_for_status()
    for p in r.json().get("places", []):
        nome = (p.get("displayName") or {}).get("text", "")
        comp = {t: c.get("longText") for c in p.get("addressComponents", []) for t in c.get("types", [])}
        loc = p.get("location") or {}
        la, lo = loc.get("latitude"), loc.get("longitude")
        if la is None or not _dentro_poa(la, lo):
            continue
        sim = _parecido(emp_original, nome + " " + p.get("formattedAddress", ""))
        bairro_res = comp.get("sublocality_level_1") or comp.get("sublocality") or ""
        mesmo_bairro = bool(bairro) and _sem_acento(bairro) in _sem_acento(bairro_res + " " + p.get("formattedAddress", ""))
        if sim < 0.5 and not (sim >= 0.34 and mesmo_bairro):
            continue
        rua, num = comp.get("route"), comp.get("street_number")
        return {"endereco": f"{rua}, {num}" if rua and num else rua, "numero": num,
                "latitude": la, "longitude": lo, "nome_google": nome,
                "bairro_google": bairro_res, "fonte": "google", "em": _hoje()}
    return None

def _nominatim(emp_original, bairro):
    q = ", ".join(x for x in (emp_original, bairro, "Porto Alegre", "Brasil") if x)
    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params={"q": q, "format": "json", "limit": 1, "countrycodes": "br", "addressdetails": 1},
                     headers=UA, timeout=20)
    res = r.json()
    if not res:
        return None
    la, lo = float(res[0]["lat"]), float(res[0]["lon"])
    if not _dentro_poa(la, lo):
        return None
    ad = res[0].get("address", {})
    rua, num = ad.get("road"), ad.get("house_number")
    return {"endereco": f"{rua}, {num}" if rua and num else rua, "numero": num,
            "latitude": la, "longitude": lo, "fonte": "osm", "em": _hoje()}

def _aplicar(l, hit, fonte, extrator):
    mudou = False
    if hit.get("endereco") and (not l.get("endereco") or (hit.get("numero") and not l.get("numero"))):
        l["endereco"] = hit["endereco"]; mudou = True
    if hit.get("numero") and not l.get("numero"):
        l["numero"] = hit["numero"]; mudou = True
    if hit.get("latitude") and not l.get("latitude"):
        l["latitude"], l["longitude"] = hit["latitude"], hit["longitude"]; mudou = True
    if mudou:
        l["endereco_fonte"] = fonte
        if extrator:
            extrator.classificar(l)
    return mudou

def resolver(listings, bairros_alvo=None):
    try:
        import extrator
    except Exception:
        extrator = None
    log = {"dicionario": 0, "resolvidos_interno": 0, "resolvidos_google": 0, "resolvidos_osm": 0,
           "google_consultas": 0, "osm_consultas": 0, "google_ativo": bool(GOOGLE_KEY)}

    # 1) dicionário interno: (prédio, bairro) -> endereço revelado por algum anúncio
    dic, por_nome = {}, {}
    for l in listings:
        emp = _norm(l.get("empreendimento"))
        if not emp or l.get("endereco_fonte"):
            continue
        if not (l.get("endereco") and l.get("numero")):
            continue
        cand = {"endereco": l["endereco"], "numero": l["numero"],
                "latitude": l.get("latitude"), "longitude": l.get("longitude")}
        dic.setdefault((emp, l.get("bairro")), cand)
        por_nome.setdefault(emp, {})[l["endereco"]] = cand
    log["dicionario"] = len(dic)

    # 2) aplica nos anúncios sem número; agrupa o que sobrar para busca externa
    pendentes = {}
    for l in listings:
        if l.get("removido_em") or (l.get("endereco") and l.get("numero")):
            continue
        emp = _norm(l.get("empreendimento"))
        if not emp:
            continue
        hit = dic.get((emp, l.get("bairro")))
        if not hit and len(por_nome.get(emp, {})) == 1:     # nome único na base: vale para qualquer bairro
            hit = next(iter(por_nome[emp].values()))
        if hit:
            if _aplicar(l, hit, "condominio", extrator):
                log["resolvidos_interno"] += 1
        else:
            pendentes.setdefault((emp, l.get("bairro") or ""), []).append(l)

    # 3) busca externa (Google se houver chave; senão OpenStreetMap), com cache
    cache = {}
    if os.path.exists(CACHE):
        try:
            cache = json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            cache = {}
    # prédios com mais anúncios primeiro
    for (emp, bairro), ls in sorted(pendentes.items(), key=lambda kv: -len(kv[1])):
        if len(_tokens(emp)) == 0 or re.search(r"\d{4,}|fechad|privativ|elevador|piscina|apto|apart", emp):
            continue                       # nome genérico/lixo do anúncio: não vale buscar
        chave = f"{emp}|{_sem_acento(bairro)}"
        hit = cache.get(chave)
        idade = 999
        if isinstance(hit, dict) and hit.get("em"):
            idade = (datetime.strptime(_hoje(), "%Y-%m-%d") - datetime.strptime(hit["em"], "%Y-%m-%d")).days
        eh_google = isinstance(hit, dict) and hit.get("fonte") == "google"
        precisa = (chave not in cache
                   or (eh_google and idade > GOOGLE_VALIDADE_DIAS)
                   or (GOOGLE_KEY and not eh_google))          # chave nova do Google: refaz o que veio do OSM
        if precisa:
            nome_original = next((l["empreendimento"] for l in ls if l.get("empreendimento")), emp)
            try:
                if GOOGLE_KEY and log["google_consultas"] < GOOGLE_CAP_EXEC:
                    res = _google(nome_original, bairro, cache)
                    if res == "cota":
                        log["google_cota_esgotada"] = True
                        continue
                    log["google_consultas"] += 1
                    cache[chave] = res or {"fonte": "google", "vazio": True, "em": _hoje()}
                    hit = res
                elif not GOOGLE_KEY and log["osm_consultas"] < NOMINATIM_CAP:
                    log["osm_consultas"] += 1
                    hit = _nominatim(nome_original, bairro)
                    cache[chave] = hit or {"fonte": "osm", "vazio": True, "em": _hoje()}
                    time.sleep(1.1)
                else:
                    continue
            except Exception as e:
                log["erro_busca"] = str(e)[:150]
                continue
        if isinstance(hit, dict) and hit.get("vazio"):
            hit = None
        if hit:
            for l in ls:
                if _aplicar(l, hit, hit.get("fonte", "osm"), extrator):
                    log["resolvidos_" + ("google" if hit.get("fonte") == "google" else "osm")] += 1
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return log
