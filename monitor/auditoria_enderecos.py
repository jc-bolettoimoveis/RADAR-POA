#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoria de endereços: amostra até N anúncios de CADA site da lista e mede
quanto de localização cada imobiliária "deixa vazar":
  - % com rua + NÚMERO       (P1 direto)
  - % com coordenada exata   (lat/long embutida no mapa — P1)
  - % com nome do prédio     (P2)
  - % só rua / só bairro
Resultado: tabela no log + data/auditoria.json + docs/auditoria.csv
Rode manualmente pelo GitHub Actions (workflow "Auditoria de endereços").
"""
import json, os, random, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monitor as m
from extrator import extrair

AMOSTRA = int(os.environ.get("AMOSTRA_POR_SITE", "10"))

def main():
    cfg = m.load_json(m.CFG_PATH, None)
    session = __import__("requests").Session()
    resultado = {}
    for site in cfg["sites"]:
        if not site.get("enabled"):
            continue
        nome = site["nome"]
        print(f"== {nome}")
        stats = {"amostra": 0, "com_numero": 0, "com_coordenada": 0,
                 "com_empreendimento": 0, "so_rua": 0, "so_bairro": 0, "erro": None}
        try:
            urls = m.collect_site_urls(site, session, {})
            props = sorted(u for u in urls if m.is_property_url(u, site))
            random.seed(42)
            amostra = random.sample(props, min(AMOSTRA, len(props))) if props else []
            for u in amostra:
                html = None
                if site.get("render"):
                    try:
                        import render_js
                        html = render_js.get_html(u)
                    except Exception:
                        html = None
                if html is None:
                    try:
                        html = m.fetch(u, session)
                    except Exception:
                        continue
                d = extrair(html, u)
                stats["amostra"] += 1
                if d.get("numero"):
                    stats["com_numero"] += 1
                if d.get("latitude"):
                    stats["com_coordenada"] += 1
                if d.get("empreendimento"):
                    stats["com_empreendimento"] += 1
                if d.get("endereco_nivel") == "rua":
                    stats["so_rua"] += 1
                if d.get("endereco_nivel") == "bairro":
                    stats["so_bairro"] += 1
                time.sleep(1.0)
        except Exception as e:
            stats["erro"] = str(e)[:150]
        resultado[nome] = stats
        n = stats["amostra"] or 1
        print(f"   amostra={stats['amostra']}  número={stats['com_numero']}/{n}  "
              f"coord={stats['com_coordenada']}/{n}  prédio={stats['com_empreendimento']}/{n}")
    m.save_json(os.path.join(m.DATA_DIR, "auditoria.json"), resultado)

    # ranking
    def pct(s, k):
        return round(100 * s[k] / s["amostra"]) if s["amostra"] else 0
    linhas = sorted(resultado.items(),
                    key=lambda kv: (pct(kv[1], "com_numero") + pct(kv[1], "com_coordenada")),
                    reverse=True)
    os.makedirs(os.path.join(m.ROOT, "docs"), exist_ok=True)
    with open(os.path.join(m.ROOT, "docs", "auditoria.csv"), "w", encoding="utf-8") as f:
        f.write("imobiliaria;amostra;% com numero;% com coordenada;% com predio;% so rua;% so bairro;erro\n")
        print("\n=========== RANKING: quem deixa o endereço vazar ===========")
        print(f"{'Imobiliária':32} {'nº':>4} {'núm%':>5} {'coord%':>6} {'prédio%':>7}")
        for nome, s in linhas:
            f.write(f"{nome};{s['amostra']};{pct(s,'com_numero')};{pct(s,'com_coordenada')};"
                    f"{pct(s,'com_empreendimento')};{pct(s,'so_rua')};{pct(s,'so_bairro')};{s['erro'] or ''}\n")
            print(f"{nome:32} {s['amostra']:>4} {pct(s,'com_numero'):>4}% {pct(s,'com_coordenada'):>5}% {pct(s,'com_empreendimento'):>6}%")

if __name__ == "__main__":
    main()
