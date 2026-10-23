"""One-time, idempotent import of the original Radar JSON history.

Requires DATABASE_URL (Supabase direct/transaction-pooler PostgreSQL URL).
No credentials are printed. Does not delete or rewrite source files.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import execute_values, Json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise SystemExit("Missing DATABASE_URL secret")

def date_or_none(value):
    if not value:
        return None
    try:
        return str(value)[:10]
    except Exception:
        return None

def number(value):
    if isinstance(value, (int, float)):
        return value
    if not value:
        return None
    import re
    m = re.search(r"[\\d.]{4,}(?:,\\d{2})?", str(value))
    if not m:
        return None
    try:
        return float(m.group().replace(".", "").replace(",", "."))
    except ValueError:
        return None

def main():
    listings = json.loads((DATA / "listings.json").read_text(encoding="utf-8"))
    known = json.loads((DATA / "known_urls.json").read_text(encoding="utf-8"))
    print(f"Source counts: listings={len(listings)}, known_sites={len(known)}")
    if not listings or not known:
        raise SystemExit("Source data missing; refusing empty import")
    conn = psycopg2.connect(DB_URL, connect_timeout=30, sslmode="require")
    try:
        with conn:
            with conn.cursor() as cur:
                for offset in range(0, len(listings), 500):
                    batch = listings[offset:offset + 500]
                    values = []
                    for item in batch:
                        url = item.get("url")
                        if not url:
                            continue
                        values.append((
                            url, item.get("site_id"), item.get("imobiliaria"),
                            item.get("tipo"), item.get("bairro"), item.get("titulo"),
                            date_or_none(item.get("detectado_em")),
                            date_or_none(item.get("removido_em")),
                            date_or_none(item.get("ultima_verificacao")),
                            str(item.get("preco")) if item.get("preco") is not None else None,
                            number(item.get("preco_venda")) or number(item.get("preco")),
                            Json(item)
                        ))
                    execute_values(cur, """
                        insert into radar_private.listings
                        (url,site_id,imobiliaria,tipo,bairro,titulo,detectado_em,
                         removido_em,ultima_verificacao,preco_texto,preco_num,payload)
                        values %s
                        on conflict(url) do update set
                        site_id=excluded.site_id, imobiliaria=excluded.imobiliaria,
                        tipo=excluded.tipo,bairro=excluded.bairro,titulo=excluded.titulo,
                        detectado_em=excluded.detectado_em,removido_em=excluded.removido_em,
                        ultima_verificacao=excluded.ultima_verificacao,
                        preco_texto=excluded.preco_texto,preco_num=excluded.preco_num,
                        payload=excluded.payload,updated_at=now()
                    """, values, page_size=500)
                    print(f"Imported listings: {min(offset+500,len(listings))}/{len(listings)}")
                for sid, urls in known.items():
                    for offset in range(0, len(urls), 1000):
                        vals = [(sid, u) for u in urls[offset:offset + 1000]]
                        execute_values(cur, """
                            insert into radar_private.known_urls(site_id,url)
                            values %s on conflict do nothing
                        """, vals, page_size=1000)
                cur.execute("select count(*) from radar_private.listings")
                count = cur.fetchone()[0]
                cur.execute("select count(*) from radar_private.known_urls")
                urls_count = cur.fetchone()[0]
                print(f"Database totals: listings={count}, known_urls={urls_count}")
                if count < len({i.get("url") for i in listings if i.get("url")}):
                    raise RuntimeError("Validation failed: missing unique URLs")
        print("Import committed successfully")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
