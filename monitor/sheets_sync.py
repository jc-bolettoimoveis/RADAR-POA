#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sincroniza a fila de captação (com dados sensíveis) para uma Google Sheet PRIVADA.
Usa um webhook do Google Apps Script — sem biblioteca pesada, sem OAuth complexo.

Configuração (secrets do GitHub):
  SHEETS_WEBHOOK_URL  -> URL do Apps Script publicado como Web App
  SHEETS_TOKEN        -> senha combinada, validada dentro do script (evita post de terceiros)

A planilha é privada (compartilhada só com a equipe via login Google). O painel público
NUNCA recebe proprietário/telefone — só esta planilha recebe.
"""
import os, json
import requests

COLUNAS = ["detectado_em", "status", "prioridade", "tipo_imovel", "bairro",
           "endereco", "numero", "area", "dorms", "suites", "vagas",
           "preco_venda", "condominio", "iptu", "empreendimento",
           "imobiliaria", "codigo", "url", "latitude", "longitude"]

def enviar(listings):
    url = os.environ.get("SHEETS_WEBHOOK_URL", "").strip()
    token = os.environ.get("SHEETS_TOKEN", "").strip()
    if not url:
        return {"obs": "SHEETS_WEBHOOK_URL não configurado — sincronização desativada"}
    # só oportunidades acionáveis (livre/verificar), não removidos nem já captados
    linhas = []
    for l in listings:
        if l.get("removido_em") or l.get("status") == "captado":
            continue
        if l.get("status", "livre") not in ("livre", "verificar"):
            continue
        linhas.append({c: l.get(c) for c in COLUNAS})
    try:
        r = requests.post(url, json={"token": token, "colunas": COLUNAS, "linhas": linhas},
                          timeout=40)
        return {"enviadas": len(linhas), "status_http": r.status_code}
    except Exception as e:
        return {"erro": str(e)[:150], "tentou_enviar": len(linhas)}
