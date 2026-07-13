#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resolve a localização de anúncios que só citam o EMPREENDIMENTO/CONDOMÍNIO:
1. Dicionário interno: aprende o endereço de cada prédio com os anúncios que o
   revelam (qualquer imobiliária) e aplica nos que escondem. Gratuito e cresce sozinho.
2. Fallback: OpenStreetMap/Nominatim (gratuito, 1 consulta/s, com cache) para
   prédios que ninguém revelou. Resultado restrito à região de Porto Alegre.
"""
import json, os, re, time
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CACHE = os.path.join(DATA_DIR, "geocache.json")
NOMINATIM_CAP = 20          # consultas externas por execução
UA = {"User-Agent": "RadarCaptacao/1.0 (uso interno; contato via github)"}

def _norm(nome):
    if not nome:
        return None
    n = str(nome).lower().translate(str.maketrans("áàâãéêëíìóòôõúùüç", "aaaaeeeiiooooouuc"))
    n = re.sub(r"^(condominio|edificio|residencial|ed\.?)\s+", "", n.strip())
    return re.sub(r"\s+", " ", n).strip() or None

def resolver(listings, bairros_alvo=None):
    try:
        import extrator
    except Exception:
        extrator = None
    log = {"dicionario": 0, "resolvidos_interno": 0, "resolvidos_osm": 0, "osm_consultas": 0}

    # 1) dicionário interno: empreendimento -> localização conhecida
    dic = {}
    for l in listings:
        emp = _norm(l.get("empreendimento"))
        if not emp:
            continue
        tem_num = bool(l.get("numero")) and not l.get("endereco_fonte")
        tem_ll = bool(l.get("latitude")) and not l.get("endereco_fonte")
        if not (tem_num or tem_ll):
            continue
        atual = dic.get(emp)
        cand = {"endereco": l.get("endereco"), "numero": l.get("numero"),
                "latitude": l.get("latitude"), "longitude": l.get("longitude"),
                "bairro": l.get("bairro")}
        if atual is None or (cand["numero"] and not atual.get("numero")):
            dic[emp] = cand
    log["dicionario"] = len(dic)

    # 2) aplica o dicionário nos anúncios sem localização completa
    pendentes = {}
    for l in listings:
        if l.get("endereco_nivel") == "completo" or l.get("removido_em"):
            continue
        emp = _norm(l.get("empreendimento"))
        if not emp:
            continue
        hit = dic.get(emp)
        if hit:
            if hit.get("endereco") and not l.get("endereco"):
                l["endereco"] = hit["endereco"]
            if hit.get("numero") and not l.get("numero"):
                l["numero"] = hit["numero"]
            if hit.get("latitude") and not l.get("latitude"):
                l["latitude"], l["longitude"] = hit["latitude"], hit["longitude"]
            l["endereco_fonte"] = "condominio"
            if extrator:
                extrator.classificar(l)
            log["resolvidos_interno"] += 1
        else:
            pendentes.setdefault(emp, []).append(l)

    # 3) fallback OpenStreetMap p/ prédios não resolvidos (com cache persistente)
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding="utf-8"))
    consultas = 0
    for emp, ls in pendentes.items():
        if emp in cache:
            hit = cache[emp]
        elif consultas >= NOMINATIM_CAP:
            continue
        else:
            consultas += 1
            hit = None
            bairro = next((l.get("bairro") for l in ls if l.get("bairro")), "")
            q = f"{emp}, {bairro}, Porto Alegre, Brasil".replace(", ,", ",")
            try:
                r = requests.get("https://nominatim.openstreetmap.org/search",
                                 params={"q": q, "format": "json", "limit": 1,
                                         "countrycodes": "br"},
                                 headers=UA, timeout=20)
                res = r.json()
                if res:
                    la, lo = float(res[0]["lat"]), float(res[0]["lon"])
                    if -30.30 < la < -29.85 and -51.35 < lo < -51.05:   # Grande POA
                        hit = {"latitude": la, "longitude": lo,
                               "endereco": res[0].get("display_name", "").split(",")[0]}
            except Exception:
                hit = None
            cache[emp] = hit
            time.sleep(1.1)
        if hit:
            for l in ls:
                if not l.get("latitude"):
                    l["latitude"], l["longitude"] = hit["latitude"], hit["longitude"]
                if hit.get("endereco") and not l.get("endereco"):
                    l["endereco"] = hit["endereco"]
                l["endereco_fonte"] = "osm"
                if extrator:
                    extrator.classificar(l)
                log["resolvidos_osm"] += 1
    log["osm_consultas"] = consultas
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return log
