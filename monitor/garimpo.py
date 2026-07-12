#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garimpo do estoque: processa em lotes os imóveis da LINHA DE BASE (os ~55 mil já
conhecidos) que ainda não viraram card — busca a ficha, filtra bairros-alvo,
cruza com a base própria/RGI e coloca os LIVRES no painel como oportunidades.

Prioridade da fila: 1º anúncios cujo slug cita bairro-alvo; entre eles, casas e
terrenos primeiro (potenciais P1). Roda em lotes (padrão 2000/execução) até
esgotar o backlog; depois só processa o que o radar adicionar de novo.
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monitor as m
import requests

BATCH = int(os.environ.get("GARIMPO_LOTE", "2000"))
DELAY = 0.7

def main():
    cfg = m.load_json(m.CFG_PATH, None)
    bairros = cfg["bairros_alvo"]
    monitorar = cfg["monitorar"]
    somente_alvo = cfg.get("somente_bairros_alvo", True)
    known = m.load_json(os.path.join(m.DATA_DIR, "known_urls.json"), {})
    listings = m.load_json(os.path.join(m.DATA_DIR, "listings.json"), [])
    listing_urls = {l["url"] for l in listings}
    feito = m.load_json(os.path.join(m.DATA_DIR, "garimpo_feito.json"), {})
    falhas = m.load_json(os.path.join(m.DATA_DIR, "garimpo_falhas.json"), {})
    nomes = {s["id"]: s["nome"] for s in cfg["sites"]}
    ativos_ids = {s["id"] for s in cfg["sites"] if s.get("enabled")}
    scfg = {s["id"]: s for s in cfg["sites"]}
    render_ids = {s["id"] for s in cfg["sites"] if s.get("render") and s.get("enabled")}
    session = requests.Session()

    variantes = [v.replace(" ", "-") for vs in bairros.values() for v in vs] + \
                [v for vs in bairros.values() for v in vs]

    def prioridade_slug(u):
        s = u.lower()
        if m.LOC_PAT.search(s) and not monitorar.get("locacao"):
            return None                      # locação com módulo desligado: pula
        alvo = 0 if any(v in s for v in variantes) else 1
        casa = 0 if re.search(r"casa|terreno|sobrado", s) else 1
        return (alvo, casa)

    # monta fila priorizada, intercalando sites p/ espalhar a carga
    filas = {}
    for sid, urls in known.items():
        if sid not in ativos_ids:
            continue          # site desativado não entra no garimpo
        ja = set(feito.get(sid, []))
        pend = []
        for u in urls:
            if u in listing_urls or u in ja:
                continue
            if not m.is_property_url(u, scfg.get(sid, {})):
                ja.add(u)         # lixo herdado (ex.: páginas de busca): descarta
                continue
            pr = prioridade_slug(u)
            if pr is None:
                ja.add(u)                    # marca como visto (não interessa)
                continue
            pend.append((pr, u))
        pend.sort()
        filas[sid] = [u for _, u in pend]
        feito[sid] = sorted(ja)

    total_pend = sum(len(f) for f in filas.values())
    print(f"Backlog restante: {total_pend} anúncios a garimpar")

    processados = aproveitados = 0
    hoje = m.today()
    while processados < BATCH and any(filas.values()):
        for sid, fila in filas.items():
            if not fila or processados >= BATCH:
                continue
            u = fila.pop(0)
            processados += 1
            info, tipo_html = m.enrich(u, session, bairros, render=sid in render_ids)
            ficha_vazia = not any(info.get(k) for k in ("titulo", "preco", "dorms", "foto", "preco_venda"))
            if ficha_vazia:
                falhas[u] = falhas.get(u, 0) + 1
                if falhas[u] < 2:
                    continue      # leitura falhou: NÃO cadastra nem marca; tenta no próximo lote
                feito.setdefault(sid, []).append(u)   # falhou 2x: desiste desta URL
                continue
            feito.setdefault(sid, []).append(u)
            tipo = m.url_tipo(u)
            if tipo == "indefinido" and tipo_html:
                tipo = tipo_html
            if tipo == "locacao" and not monitorar.get("locacao"):
                continue
            bairro = info.get("bairro")
            if somente_alvo and bairro is None and info.get("titulo"):
                continue                     # ficha lida e fora da região
            listings.append({
                "url": u, "site_id": sid, "imobiliaria": nomes.get(sid, sid),
                "tipo": tipo, "bairro": bairro,
                "titulo": info.get("titulo"), "foto": info.get("foto"),
                "preco": info.get("preco"), "descricao": info.get("descricao"),
                "detectado_em": hoje, "ultima_verificacao": hoje,
                "origem": "garimpo",
                **{k: info.get(k) for k in m.FICHA_CAMPOS},
            })
            listing_urls.add(u)
            aproveitados += 1
            time.sleep(DELAY)
    print(f"Processados {processados}, aproveitados {aproveitados}")

    # cruzamento p/ marcar livre/verificar/captado
    try:
        import cruzamento
        czlog = cruzamento.executar(cfg, listings, session, m.fetch,
                                    m.collect_site_urls, m.enrich, m.match_bairro, hoje)
        print("Cruzamento:", json.dumps(czlog, ensure_ascii=False))
    except Exception as e:
        print("Cruzamento falhou:", e)

    m.save_json(os.path.join(m.DATA_DIR, "listings.json"), listings)
    m.save_json(os.path.join(m.DATA_DIR, "garimpo_feito.json"), feito)
    m.save_json(os.path.join(m.DATA_DIR, "garimpo_falhas.json"), falhas)

    # resumo único no WhatsApp (sem spam)
    novos_g = [l for l in listings if l.get("origem") == "garimpo" and l.get("detectado_em") == hoje]
    livres = [l for l in novos_g if l.get("status", "livre") == "livre"]
    p1 = sum(1 for l in livres if l.get("prioridade") == 1)
    p2 = sum(1 for l in livres if l.get("prioridade") == 2)
    if livres:
        try:
            import alertas
            painel = os.environ.get("PAINEL_URL", "")
            alertas.enviar_texto(
                f"🗄 Garimpo do estoque: {len(livres)} oportunidade(s) LIVRE(S) adicionada(s) "
                f"ao painel (🎯P1: {p1} · 📍P2: {p2}). Backlog restante: "
                f"{max(0, total_pend - processados)}." + (f"\n📊 {painel}" if painel else ""))
        except Exception as e:
            print("alerta resumo falhou:", e)

if __name__ == "__main__":
    main()
