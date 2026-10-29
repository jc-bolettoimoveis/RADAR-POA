#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ajustes únicos nos dados, aplicados automaticamente na primeira execução após a atualização.
Cada migração roda uma vez só (registro em data/migracoes.json)."""
import json, os

def _aux_2026_10(m, cfg, listings, known, feito, falhas):
    """Auxiliadora Predial: URL canônica, bairro correto (a marca era lida como bairro)
    e desfaz remoções falsas causadas pela coleta parcial."""
    site = next((s for s in cfg["sites"] if s["id"] == "auxiliadora"), None)
    if not site:
        return {}
    ba = cfg["bairros_alvo"]
    can = lambda u: m.canonica(u, site) if "auxiliadorapredial" in u else u
    known["auxiliadora"] = sorted({can(u) for u in known.get("auxiliadora", [])})
    feito["auxiliadora"] = sorted({can(u) for u in feito.get("auxiliadora", [])})
    for u in list(falhas):
        if "auxiliadorapredial" in u:
            falhas[can(u)] = falhas.pop(u)
    novo, vistos, r = [], set(), {"fora_regiao": 0, "bairro_corrigido": 0, "reativados": 0}
    for l in listings:
        if l.get("site_id") != "auxiliadora":
            novo.append(l)
            continue
        l["url"] = can(l["url"])
        if l["url"] in vistos:
            continue
        vistos.add(l["url"])
        b = m.match_bairro(l.get("titulo"), ba) or m.match_bairro(l["url"], ba)
        if b is None and l.get("titulo"):
            r["fora_regiao"] += 1
            feito["auxiliadora"].append(l["url"])
            continue
        if b != l.get("bairro"):
            r["bairro_corrigido"] += 1
            l["bairro"] = b
        if l.pop("removido_em", None):
            r["reativados"] += 1
        l["faltas"] = 0
        novo.append(l)
    feito["auxiliadora"] = sorted(set(feito["auxiliadora"]))
    listings[:] = novo
    return r

MIGRACOES = [("auxiliadora_2026_10", _aux_2026_10)]

def aplicar(m, cfg, listings, known, feito=None, falhas=None):
    """Aplica as migrações pendentes. Se feito/falhas não vierem, lê e grava do disco."""
    reg_path = os.path.join(m.DATA_DIR, "migracoes.json")
    feitas = m.load_json(reg_path, {})
    pend = [(k, f) for k, f in MIGRACOES if k not in feitas]
    if not pend:
        return {}
    p_feito = os.path.join(m.DATA_DIR, "garimpo_feito.json")
    p_falhas = os.path.join(m.DATA_DIR, "garimpo_falhas.json")
    feito = feito if feito is not None else m.load_json(p_feito, {})
    falhas = falhas if falhas is not None else m.load_json(p_falhas, {})
    log = {}
    for k, f in pend:
        log[k] = f(m, cfg, listings, known, feito, falhas)
        feitas[k] = m.today()
        print(f"Migração {k}: {json.dumps(log[k], ensure_ascii=False)}")
    # grava tudo já, para a migração não se perder se a execução cair no meio
    m.save_json(p_feito, feito)
    m.save_json(p_falhas, falhas)
    m.save_json(os.path.join(m.DATA_DIR, "known_urls.json"), known)
    m.save_listings(listings)
    m.save_json(reg_path, feitas)
    return log
