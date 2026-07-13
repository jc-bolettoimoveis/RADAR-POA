#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrator de ficha completa do anúncio.
Ordem: 1) JSON-LD (schema.org) quando o site publica; 2) leitura do texto da página.
Retorna também 'completude' (0-100): quão completa está a ficha do anúncio.
"""
import json, re
import html as htmllib

VOCAB = ["churrasqueira", "piscina", "elevador", "portaria 24", "porteiro", "mobiliado",
         "semimobiliado", "semi-mobiliado", "sacada", "varanda", "terraço", "academia",
         "salão de festas", "salao de festas", "playground", "aceita pet", "pet friendly",
         "ar condicionado", "ar-condicionado", "split", "lareira", "closet", "home office",
         "quadra", "sauna", "espaço gourmet", "espaco gourmet", "jardim", "pátio", "patio",
         "solarium", "bicicletário", "bicicletario", "gerador", "água quente", "aquecimento",
         "vista", "andar alto", "de frente", "silencioso", "reformado", "novo", "lavabo",
         "dependência", "dependencia", "adega", "brinquedoteca", "coworking", "rooftop"]

MOEDA = r"R\$\s?([\d\.]{1,12}(?:,\d{2})?)"

def _num_br(s):
    if s is None:
        return None
    s = str(s).strip().replace("R$", "").strip()
    try:
        if "," in s:
            return float(s.replace(".", "").replace(",", "."))
        if s.count(".") == 1 and len(s.split(".")[1]) <= 2:  # 1500.50
            return float(s)
        return float(s.replace(".", ""))
    except ValueError:
        return None

def _fmt_moeda(v):
    if v is None:
        return None
    return "R$ " + f"{v:,.0f}".replace(",", ".")

def _texto(html):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmllib.unescape(t))

def _perto(texto, chave, janela=80):
    m = re.search(chave + r".{0,%d}?" % janela + MOEDA, texto, re.I | re.S)
    return _num_br(m.group(1)) if m else None

def _int_perto(texto, pat):
    m = re.search(pat, texto, re.I)
    return int(m.group(1)) if m else None

# --------------------------------------------------------------- JSON-LD
def _walk(obj, out):
    if isinstance(obj, dict):
        t = str(obj.get("@type", "")).lower()
        if "offer" in t or "price" in str(obj.keys()).lower():
            p = obj.get("price") or (obj.get("priceSpecification") or {}).get("price")
            if p and not out.get("preco_venda"):
                out["preco_venda"] = _num_br(p)
        for k, v in obj.items():
            kl = k.lower()
            if kl in ("numberofrooms", "numberofbedrooms") and v:
                out.setdefault("dorms", int(float(str(v).split()[0])) if str(v)[:1].isdigit() else None)
            elif kl == "numberofbathroomstotal" and v:
                out.setdefault("banheiros", int(float(v)))
            elif kl == "floorsize" and isinstance(v, dict) and v.get("value"):
                out.setdefault("area", _num_br(v["value"]))
            elif kl == "address":
                if isinstance(v, dict):
                    out.setdefault("endereco", ", ".join(
                        str(v.get(c)) for c in ("streetAddress", "addressLocality") if v.get(c)))
                elif isinstance(v, str):
                    out.setdefault("endereco", v)
            elif kl == "image" and v and not out.get("foto_jl"):
                out["foto_jl"] = v[0] if isinstance(v, list) and v else (v if isinstance(v, str) else None)
            elif kl in ("sku", "productid", "identifier") and v and not out.get("codigo"):
                out["codigo"] = str(v)[:30]
            _walk(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _walk(x, out)

def _jsonld(html):
    out = {}
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            _walk(json.loads(m.group(1).strip()), out)
        except Exception:
            continue
    return out

# ordem importa: específicos antes dos genéricos ("apartamento garden" → garden)
TIPOS_IMOVEL = ["casa em condominio", "casa em condomínio", "casa comercial", "sobrado",
                "garden", "cobertura", "duplex", "triplex", "loft", "studio", "kitnet",
                "jk", "flat", "apartamento", "conjunto comercial", "conjunto", "sala",
                "loja", "ponto comercial", "casa", "terreno", "lote", "galpão", "galpao",
                "pavilhão", "pavilhao", "depósito", "deposito", "prédio", "predio",
                "box", "garagem", "fração", "fracao", "sítio", "sitio", "chácara", "chacara"]

def _latlong(html):
    pats = [
        r'"lat(?:itude)?"\s*[:=]\s*"?(-?\d{1,2}\.\d{3,})"?\s*[,}].{0,120}?"l(?:o?ng|ongitude)"\s*[:=]\s*"?(-?\d{1,3}\.\d{3,})',
        r'LatLng\(\s*(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})',
        r'[?&]q=(-?\d{1,2}\.\d{3,}),\s*(-?\d{1,3}\.\d{3,})',
        r'data-lat(?:itude)?=["\'](-?\d{1,2}\.\d{3,})["\'][^>]{0,120}data-l(?:o?ng|ongitude)=["\'](-?\d{1,3}\.\d{3,})',
        r'center=(-?\d{1,2}\.\d{3,})%2C(-?\d{1,3}\.\d{3,})',
    ]
    for p in pats:
        m = re.search(p, html, re.I | re.S)
        if m:
            try:
                la, lo = float(m.group(1)), float(m.group(2))
            except ValueError:
                continue
            if -34.5 < la < -27.0 and -58.0 < lo < -49.0:   # plausível no RS
                return la, lo
    return None

def _empreendimento(texto):
    PARA = r"(?!(?:Rua|Av|Avenida|Travessa|Alameda|Estrada|Localizado|Situado|Em|No|Na)\b)"
    m = re.search(r"(?:Condom[íi]nio|Edif[íi]cio|Residencial|Ed\.)\s+(" + PARA +
                  r"[A-ZÀ-Ü][\w'À-ü-]+(?:\s+" + PARA + r"[A-ZÀ-Ü0-9][\w'À-ü-]+){0,3})", texto)
    return m.group(1).strip() if m else None

CANONICO = {
    "garden": "apartamento garden", "casa em condominio": "casa em condomínio",
    "galpao": "galpão", "predio": "prédio", "pavilhao": "pavilhão",
    "deposito": "depósito", "fracao": "fração", "sitio": "sítio",
    "chacara": "chácara", "lote": "terreno", "jk": "apartamento jk",
    "kitnet": "kitnet", "ponto comercial": "loja",
}

def _tipo_imovel(texto):
    tl = (texto or "").lower()
    for t in TIPOS_IMOVEL:
        if t in tl:
            return CANONICO.get(t, t)
    return None

FOTO_RUIM = re.compile(r"logo|logotipo|icon|avatar|whatsapp|placeholder|selo|favicon|marca|og-?image-?default|\.svg", re.I)
FOTO_BOA = re.compile(r"upload|foto|imove|galeria|gallery|cdn|media|storage|arquivo|imagem|thumb|cloudfront|amazonaws|jetimgs", re.I)

def escolher_foto(html, foto_jl=None, foto_og=None):
    """Prefere foto real do imóvel; descarta logos/placeholder."""
    cands = []
    for f in (foto_jl, foto_og):
        if f:
            cands.append(f)
    cands += re.findall(r'<img[^>]+src=["\']([^"\'>]+)', html, re.I)[:60]
    for c in cands:
        if not FOTO_RUIM.search(c) and FOTO_BOA.search(c) and re.search(r"\.(jpe?g|webp|png)([?#]|$)", c, re.I):
            return c
    for c in cands:
        if not FOTO_RUIM.search(c) and re.search(r"\.(jpe?g|webp)([?#]|$)", c, re.I):
            return c
    return None

def classificar(d):
    """(Re)calcula endereco_nivel e prioridade a partir dos campos atuais."""
    tem_rua = bool(d.get("endereco"))
    tem_ll = bool(d.get("latitude"))
    if (tem_rua and d.get("numero")) or tem_ll:
        d["endereco_nivel"] = "completo"
    elif tem_rua and d.get("empreendimento"):
        d["endereco_nivel"] = "rua+condominio"
    elif tem_rua:
        d["endereco_nivel"] = "rua"
    else:
        d["endereco_nivel"] = "bairro"
    casa_terreno = (d.get("tipo_imovel") or "") in ("casa", "sobrado", "terreno")
    if d["endereco_nivel"] == "completo":
        d["prioridade"] = 1 if casa_terreno else 2
    elif d["endereco_nivel"] == "rua+condominio":
        d["prioridade"] = 2
    elif d["endereco_nivel"] == "rua":
        d["prioridade"] = 3
    else:
        d["prioridade"] = 4
    return d

# --------------------------------------------------------------- principal
def extrair(html, url=""):
    d = _jsonld(html)
    texto = _texto(html)[:120000]

    d.setdefault("dorms", _int_perto(texto, r"(\d+)\s*(?:dormit[óo]rio|quarto)"))
    d.setdefault("suites", _int_perto(texto, r"(\d+)\s*su[íi]te"))
    d.setdefault("vagas", _int_perto(texto, r"(\d+)\s*(?:vaga|box(?:es)?\b|garag)"))
    d.setdefault("banheiros", _int_perto(texto, r"(\d+)\s*banheiro"))

    if not d.get("area"):
        m = (re.search(r"[áa]rea\s+(?:privativa|[úu]til)\D{0,15}(\d{2,4}(?:[.,]\d{1,2})?)\s*m", texto, re.I)
             or re.search(r"(\d{2,4}(?:[.,]\d{1,2})?)\s*m[²2]", texto))
        d["area"] = _num_br(m.group(1)) if m else None
    m = re.search(r"[áa]rea\s+total\D{0,15}(\d{2,4}(?:[.,]\d{1,2})?)\s*m", texto, re.I)
    d["area_total"] = _num_br(m.group(1)) if m else None

    d["condominio"] = _perto(texto, r"condom[íi]nio")
    d["iptu"] = _perto(texto, r"iptu")
    if not d.get("preco_venda"):
        d["preco_venda"] = _perto(texto, r"(?:venda|compra|por apenas|valor)")
    d["preco_locacao"] = _perto(texto, r"(?:aluguel|loca[çc][ãa]o|/\s*m[êe]s)")
    if not d.get("preco_venda"):
        # maior valor monetário plausível da página (>= R$ 80 mil) como preço de venda
        vals = [_num_br(v) for v in re.findall(MOEDA, texto)]
        vals = [v for v in vals if v and v >= 80000]
        d["preco_venda"] = max(vals) if vals else None
    # condomínio/IPTU não podem "vazar" para preço
    for k in ("condominio", "iptu"):
        if d.get(k) and d.get("preco_venda") and d[k] == d["preco_venda"]:
            d[k] = None

    if not d.get("codigo"):
        m = re.search(r"(?:refer[êe]ncia|c[óo]d(?:igo)?\.?|ref\.?)[:\s#]{0,3}([A-Z]{0,4}\d{2,8})", texto, re.I)
        d["codigo"] = m.group(1) if m else None
    if not d.get("endereco"):
        m = re.search(r"((?:Rua|Av\.?|Avenida|Travessa|Alameda|Estrada)\s[^,\.;]{4,60}(?:,\s?\d{1,5})?)", texto)
        d["endereco"] = m.group(1).strip() if m else None

    # ------- localização detalhada -------
    ll = _latlong(html)
    d["latitude"], d["longitude"] = (ll if ll else (None, None))
    d["empreendimento"] = _empreendimento(texto)
    d["tipo_imovel"] = _tipo_imovel((d.get("endereco") or "") + " " + texto[:3000]) or _tipo_imovel(url)
    m = re.search(r",\s?(\d{1,5})(?:\D|$)", d.get("endereco") or "")
    d["numero"] = m.group(1) if m else None
    classificar(d)
    casa_terreno = (d.get("tipo_imovel") or "") in ("casa", "sobrado", "terreno")
    if d["endereco_nivel"] == "completo":
        d["prioridade"] = 1 if casa_terreno else 2
    elif d["endereco_nivel"] == "rua+condominio":
        d["prioridade"] = 2
    elif d["endereco_nivel"] == "rua":
        d["prioridade"] = 3
    else:
        d["prioridade"] = 4

    tl = texto.lower()
    carac = sorted({c for c in VOCAB if c in tl})
    d["caracteristicas"] = carac or None

    d["foto_boa"] = escolher_foto(html, d.pop("foto_jl", None))

    # formata moedas para exibição
    d["preco_venda_fmt"] = _fmt_moeda(d.get("preco_venda"))
    d["preco_locacao_fmt"] = _fmt_moeda(d.get("preco_locacao"))
    d["condominio_fmt"] = _fmt_moeda(d.get("condominio"))
    d["iptu_fmt"] = _fmt_moeda(d.get("iptu"))

    # completude da ficha (15 campos)
    campos = ["dorms", "suites", "vagas", "banheiros", "area", "preco_venda",
              "condominio", "iptu", "codigo", "endereco"]
    pontos = sum(1 for c in campos if d.get(c))
    pontos += min(3, len(carac)) if carac else 0          # até 3 pontos por características
    pontos += 1 if d.get("area_total") else 0
    pontos += 1 if d.get("preco_locacao") else 0
    d["completude"] = round(100 * pontos / 15)
    return d
