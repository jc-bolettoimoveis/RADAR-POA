#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coleta de URLs em sites 100% JavaScript (React/Next), usando navegador headless
(Playwright/Chromium). Usado apenas nos sites marcados com "render": true na config.
"""
from urllib.parse import urljoin, urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

def coletar(site, log):
    from playwright.sync_api import sync_playwright
    base = site["base"]
    urls = set()
    paths = site.get("listing_paths") or ["/"]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(user_agent=UA, viewport={"width": 1366, "height": 900})
        for path in paths:
            try:
                page.goto(urljoin(base, path), timeout=35000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                for _ in range(4):                      # rolagem p/ carregar lazy-load
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1200)
                hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                for h in hrefs:
                    if urlparse(h).netloc == urlparse(base).netloc:
                        urls.add(h.split("#")[0])
            except Exception as e:
                log.setdefault("render_erros", []).append(f"{path}: {str(e)[:80]}")
        browser.close()
    log["metodo"] = "render(js)"
    return urls


# --- leitura de página individual com navegador persistente (fichas de sites JS) ---
_pw = {"p": None, "browser": None, "page": None}

def get_html(url, timeout=35000):
    """Retorna o HTML já renderizado (JavaScript executado). Reutiliza o navegador."""
    from playwright.sync_api import sync_playwright
    if _pw["p"] is None:
        _pw["p"] = sync_playwright().start()
        _pw["browser"] = _pw["p"].chromium.launch(
            args=["--disable-blink-features=AutomationControlled"])
        _pw["page"] = _pw["browser"].new_page(
            user_agent=UA, viewport={"width": 1366, "height": 900})
    pg = _pw["page"]
    pg.goto(url, timeout=timeout, wait_until="domcontentloaded")
    try:
        pg.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    pg.wait_for_timeout(3500)
    # rola para forçar carregamento tardio (endereço/mapa em SPA)
    for _ in range(3):
        try: pg.mouse.wheel(0, 3000)
        except Exception: break
        pg.wait_for_timeout(900)
    # espera aparecer um logradouro no texto (até +6s)
    import re as _re
    for _ in range(6):
        if _re.search(r"(Rua|Avenida|Av\.|Travessa|Estrada|Alameda)\s+[A-ZÀ-Ü]", pg.content()):
            break
        pg.wait_for_timeout(1000)
    return pg.content()
