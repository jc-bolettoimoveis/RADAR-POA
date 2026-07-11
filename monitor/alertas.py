#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alertas do Radar via WhatsApp.

Canal 1 (padrão, grátis): CallMeBot — manda mensagem para o SEU próprio número.
  Secret WHATSAPP_DESTINOS no formato:  "5551999998888:apikey1,5551977776666:apikey2"
  (número no formato internacional sem '+', dois-pontos, apikey do CallMeBot)

Canal 2 (oficial Meta, opcional): WhatsApp Cloud API.
  Secrets: WA_META_TOKEN, WA_META_PHONE_ID, WA_META_DESTINOS ("5551999998888,5551...")

Se nenhum secret estiver configurado, o alerta é apenas impresso no log da execução.
"""
import os, json, urllib.parse
import requests

MAX_ITENS_POR_BLOCO = 8
TIMEOUT = 20

def _fmt_item(l):
    pri = {1: "🎯 P1 ENDEREÇO COMPLETO (eemovel direto!) ", 2: "📍 P2 prédio identificado "}.get(l.get("prioridade"), "")
    partes = [pri + (l.get("titulo") or l["url"].split("/")[-1].replace("-", " ")[:80])]
    specs = " · ".join(x for x in (
        f"{l['dorms']} dorm" if l.get("dorms") else None,
        f"{l['suites']} suíte(s)" if l.get("suites") else None,
        f"{l['vagas']} vaga(s)" if l.get("vagas") else None,
        f"{int(l['area'])}m²" if l.get("area") else None) if x)
    if specs:
        partes.append(specs)
    extras = " · ".join(x for x in (l.get("bairro"), l.get("preco"), l.get("imobiliaria")) if x)
    if extras:
        partes.append(extras)
    partes.append(l["url"])
    return "\n".join(partes)

def montar_mensagens(novos_livres, removidos, quedas, painel_url=None):
    """Retorna lista de mensagens (strings) prontas para envio. Vazia se nada a reportar."""
    msgs = []
    if novos_livres:
        for i in range(0, len(novos_livres), MAX_ITENS_POR_BLOCO):
            bloco = novos_livres[i:i + MAX_ITENS_POR_BLOCO]
            corpo = "\n\n".join(_fmt_item(l) for l in bloco)
            extra = f" ({i+1}-{i+len(bloco)} de {len(novos_livres)})" if len(novos_livres) > MAX_ITENS_POR_BLOCO else ""
            msgs.append(f"🟢 RADAR: {len(novos_livres)} imóvel(is) NOVO(S) livre(s) p/ captar{extra}\n\n{corpo}")
    if removidos:
        corpo = "\n\n".join(_fmt_item(l) for l in removidos[:MAX_ITENS_POR_BLOCO])
        msgs.append(f"🔴 RADAR: {len(removidos)} anúncio(s) SAIU/SAÍRAM do ar na concorrência "
                    f"(vendido ou perdeu contrato — oportunidade de contato):\n\n{corpo}")
    if quedas:
        linhas = []
        for l in quedas[:MAX_ITENS_POR_BLOCO]:
            q = l.get("queda", {})
            linhas.append(f"{(l.get('titulo') or '')[:70]}\n{q.get('de')} → {q.get('para')} · {l.get('imobiliaria')}\n{l['url']}")
        msgs.append(f"💸 RADAR: {len(quedas)} queda(s) de preço (proprietário com pressa?):\n\n" + "\n\n".join(linhas))
    if msgs and painel_url:
        msgs[-1] += f"\n\n📊 Painel completo: {painel_url}"
    return msgs

def _enviar_callmebot(msg, log):
    destinos = os.environ.get("WHATSAPP_DESTINOS", "").strip()
    if not destinos:
        return False
    ok = 0
    for par in destinos.split(","):
        par = par.strip()
        if ":" not in par:
            continue
        fone, apikey = par.split(":", 1)
        try:
            r = requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": fone.strip(), "apikey": apikey.strip(), "text": msg},
                timeout=TIMEOUT)
            if r.status_code == 200:
                ok += 1
            else:
                log.setdefault("erros", []).append(f"callmebot {fone}: HTTP {r.status_code}")
        except Exception as e:
            log.setdefault("erros", []).append(f"callmebot {fone}: {str(e)[:100]}")
    log["callmebot_enviadas"] = log.get("callmebot_enviadas", 0) + ok
    return ok > 0

def _enviar_meta(msg, log):
    token = os.environ.get("WA_META_TOKEN", "").strip()
    phone_id = os.environ.get("WA_META_PHONE_ID", "").strip()
    destinos = os.environ.get("WA_META_DESTINOS", "").strip()
    if not (token and phone_id and destinos):
        return False
    ok = 0
    for fone in destinos.split(","):
        try:
            r = requests.post(
                f"https://graph.facebook.com/v20.0/{phone_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"messaging_product": "whatsapp", "to": fone.strip(),
                      "type": "text", "text": {"body": msg[:4000]}},
                timeout=TIMEOUT)
            if r.status_code < 300:
                ok += 1
            else:
                log.setdefault("erros", []).append(f"meta {fone}: HTTP {r.status_code} {r.text[:80]}")
        except Exception as e:
            log.setdefault("erros", []).append(f"meta {fone}: {str(e)[:100]}")
    log["meta_enviadas"] = log.get("meta_enviadas", 0) + ok
    return ok > 0

def enviar(novos_livres, removidos, quedas, painel_url=None):
    log = {"mensagens": 0}
    msgs = montar_mensagens(novos_livres, removidos, quedas, painel_url)
    if not msgs:
        log["obs"] = "nada a reportar"
        return log
    log["mensagens"] = len(msgs)
    for m in msgs:
        enviado = _enviar_callmebot(m, log)
        enviado = _enviar_meta(m, log) or enviado
        if not enviado:
            log["obs"] = "nenhum canal configurado — mensagem apenas no log"
            print("---- ALERTA (não enviado) ----\n" + m + "\n------------------------------")
    return log


def enviar_texto(msg):
    """Envia uma única mensagem avulsa (resumos)."""
    log = {}
    ok = _enviar_callmebot(msg, log)
    ok = _enviar_meta(msg, log) or ok
    if not ok:
        print("---- RESUMO (não enviado) ----\n" + msg)
    return log
