#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Identifica a cidade (e o estado) de um anúncio.

Ordem das pistas: URL -> título -> endereço -> descrição -> página (JSON-LD / texto).
A primeira pista que citar uma cidade decide (dentro dela, a última cidade citada). Sem pista nenhuma, o imóvel é
considerado de Porto Alegre (a maioria dos sites monitorados só anuncia na capital),
com cidade_fonte = "presumida".

detectar(...) -> (cidade, uf, fonte)
  uf = "RS" para cidades gaúchas; sigla do estado para as de fora;
  fonte = "url" | "titulo" | "endereco" | "descricao" | "pagina" | "coordenadas" | "presumida"
"""
import re
import unicodedata

POA = "Porto Alegre"


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"%20|[-_+/|,.;:()\[\]]", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip() + " "


# ---------------------------------------------------------------- cidades do RS
# (nome de exibição, variações já normalizadas: sem acento, minúsculas, espaços)
RS = [
    (POA, ["porto alegre", "poa rs", "poa"]),
    ("Canoas", ["canoas"]),
    ("Cachoeirinha", ["cachoeirinha"]),
    ("Gravataí", ["gravatai"]),
    ("Viamão", ["viamao"]),
    ("Alvorada", ["alvorada rs", "em alvorada", "alvorada"]),
    ("Esteio", ["esteio"]),
    ("Sapucaia do Sul", ["sapucaia do sul", "sapucaia"]),
    ("São Leopoldo", ["sao leopoldo"]),
    ("Novo Hamburgo", ["novo hamburgo"]),
    ("Campo Bom", ["campo bom"]),
    ("Estância Velha", ["estancia velha"]),
    ("Sapiranga", ["sapiranga"]),
    ("Guaíba", ["guaiba rs", "em guaiba", "cidade de guaiba"]),
    ("Eldorado do Sul", ["eldorado do sul"]),
    ("Nova Santa Rita", ["nova santa rita"]),
    ("Glorinha", ["glorinha"]),
    ("Montenegro", ["montenegro"]),
    ("Charqueadas", ["charqueadas"]),
    ("Xangri-lá", ["xangri la", "xangrila"]),
    ("Capão da Canoa", ["capao da canoa"]),
    ("Atlântida", ["atlantida sul", "atlantida xangri la", "atlantida rs", "em atlantida"]),
    ("Tramandaí", ["tramandai"]),
    ("Imbé", ["imbe"]),
    ("Osório", ["osorio rs", "em osorio"]),
    ("Torres", ["torres rs", "em torres"]),
    ("Arroio do Sal", ["arroio do sal"]),
    ("Cidreira", ["cidreira"]),
    ("Balneário Pinhal", ["balneario pinhal"]),
    ("Gramado", ["gramado rs", "em gramado", "centro gramado"]),
    ("Canela", ["canela rs", "em canela"]),
    ("Nova Petrópolis", ["nova petropolis"]),
    ("Bento Gonçalves", ["bento goncalves"]),
    ("Garibaldi", ["garibaldi rs", "em garibaldi"]),
    ("Caxias do Sul", ["caxias do sul"]),
    ("Santa Cruz do Sul", ["santa cruz do sul"]),
    ("Lajeado", ["lajeado"]),
    ("Santa Maria", ["santa maria rs", "em santa maria"]),
    ("Pelotas", ["pelotas"]),
    ("Rio Grande", ["rio grande rs", "cidade de rio grande"]),
    ("Passo Fundo", ["passo fundo"]),
    ("Taquara", ["taquara rs", "em taquara"]),
    ("Igrejinha", ["igrejinha"]),
    ("Parobé", ["parobe"]),
    ("Dois Irmãos", ["dois irmaos"]),
    ("Ivoti", ["ivoti"]),
    ("Portão", ["portao rs", "em portao"]),
    ("Triunfo", ["triunfo rs", "em triunfo"]),
    ("Barra do Ribeiro", ["barra do ribeiro"]),
    ("Cambará do Sul", ["cambara do sul"]),
    ("São Francisco de Paula", ["sao francisco de paula"]),
    ("Farroupilha", ["farroupilha rs", "em farroupilha"]),
    ("Flores da Cunha", ["flores da cunha"]),
    ("Venâncio Aires", ["venancio aires"]),
    ("Camaquã", ["camaqua"]),
    ("Santo Antônio da Patrulha", ["santo antonio da patrulha"]),
    ("Balneário Atlântico", ["balneario atlantico"]),
]

# ---------------------------------------------------------------- fora do RS
FORA = [
    ("São Paulo", "SP", ["sao paulo"]),
    ("Porto Feliz", "SP", ["porto feliz"]),
    ("Campinas", "SP", ["campinas"]),
    ("Itu", "SP", ["itu sp"]),
    ("Curitiba", "PR", ["curitiba"]),
    ("São José dos Pinhais", "PR", ["sao jose dos pinhais"]),
    ("Florianópolis", "SC", ["florianopolis", "floripa"]),
    ("Balneário Camboriú", "SC", ["balneario camboriu", "camboriu"]),
    ("Itapema", "SC", ["itapema"]),
    ("Itajaí", "SC", ["itajai"]),
    ("Bombinhas", "SC", ["bombinhas"]),
    ("Garopaba", "SC", ["garopaba"]),
    ("Joinville", "SC", ["joinville"]),
    ("Rio de Janeiro", "RJ", ["rio de janeiro"]),
    ("Belo Horizonte", "MG", ["belo horizonte"]),
    ("Porto Belo", "SC", ["porto belo"]),
    ("Governador Celso Ramos", "SC", ["governador celso ramos"]),
    ("Fortaleza", "CE", ["fortaleza ce", "fortaleza foxter", "em fortaleza"]),
    ("Manaus", "AM", ["manaus"]),
    ("Salvador", "BA", ["salvador ba", "em salvador"]),
    ("Goiânia", "GO", ["goiania"]),
    ("Recife", "PE", ["recife"]),
    ("Natal", "RN", ["natal rn"]),
    ("Exterior", "EX", ["imoveis internacionais", "miami", "orlando", "punta del este", "jose ignacio",
                        "lisboa", "portugal", "uruguai", "montevideo", "estados unidos", "usa fl"]),
]

UFS = ("sp", "sc", "pr", "rj", "mg", "df", "fl")
# sigla de estado como palavra solta (ex.: "...-sao-paulo-sp-...", "Campinas/SP", "(SC)")
UF_PAT = re.compile(r" (%s) " % "|".join(UFS))

# Retira expressões que citam nome de cidade sem ser a localização do imóvel
RUIDO = re.compile(r" rio grande do sul | grande porto alegre | regiao metropolitana de porto alegre "
                   r"| av(?:enida)? porto alegre | rua porto alegre | rua canoas | av(?:enida)? canoas "
                   r"| rua gramado | rua torres | rua esteio | rua guaiba | rua montenegro | av(?:enida)? montenegro "
                   r"| rua santa maria | rua pelotas | rua sao paulo | rua curitiba | rua florianopolis "
                   r"| santa maria goretti | rua alvorada | edificio alvorada | av(?:enida)? sao paulo | av(?:enida)? florianopolis | travessa [a-z ]{3,25}? ")

_TABELA = [(nome, "RS", var) for nome, vs in RS for var in vs] + \
          [(nome, uf, var) for nome, uf, vs in FORA for var in vs]
# variações mais longas primeiro ("nova petropolis" antes de "petropolis", "sapucaia do sul" antes de "sapucaia")
_TABELA.sort(key=lambda t: -len(t[2]))


def _achar(texto, permite_uf=True, estrito=False, rs_generico=False):
    """Retorna (cidade, uf) da última cidade citada no texto, ou None.
    estrito=True (descrições): só vale "em X" ou "X rs"/"X sp"."""
    t = RUIDO.sub(" ", _norm(texto))
    t = t.replace(" canoas estancia velha ", " canoas ")   # Estância Velha também é bairro de Canoas
    if t.strip() == "":
        return None
    melhor = None
    for nome, uf, var in _TABELA:
        # na URL/título a cidade costuma vir DEPOIS do bairro/prédio
        # ("condominio-itapema-bom-fim-porto-alegre", "Guarujá, Porto Alegre"): vale a última citação.
        # Na descrição (estrito), vale a primeira citação no formato "em X".
        i = t.find(" " + var + " ") if estrito else t.rfind(" " + var + " ")
        if i >= 0 and estrito:
            ok = False
            for mm in re.finditer(r"(?= %s )" % re.escape(var), t):
                j = mm.start()
                antes, depois = t[max(0, j - 4):j + 1], t[j + len(var) + 1:j + len(var) + 5]
                if antes.endswith(" em ") or depois in (" rs ", " sp ", " sc ", " pr "):
                    i, ok = j, True
                    break
            if not ok:
                i = -1
        if i >= 0 and (melhor is None or (i < melhor[0] if estrito else i > melhor[0])):
            melhor = (i, nome, uf)
    if melhor:
        return melhor[1], melhor[2]
    if permite_uf:
        m = UF_PAT.search(t)
        if m:
            uf = "EX" if m.group(1) == "fl" else m.group(1).upper()
            return ("Exterior" if uf == "EX" else "Outra cidade (%s)" % uf), uf
        if rs_generico and re.search(r" rs (?!\d)", t):           # "...-cidade-rs-..." de cidade gaúcha fora da lista
            return "Outra cidade (RS)", "RS"
    return None


def _da_pagina(html):
    """Cidade declarada pelo próprio site: JSON-LD addressLocality / addressRegion."""
    if not html:
        return None
    loc = re.search(r'"addressLocality"\s*:\s*"([^"]{2,60})"', html)
    if loc:
        r = _achar(loc.group(1), permite_uf=False)
        if r:
            return r
    reg = re.search(r'"addressRegion"\s*:\s*"([A-Za-z ]{2,25})"', html)
    if reg:
        sig = _norm(reg.group(1)).strip()
        if sig in UFS or sig in ("sao paulo", "santa catarina", "parana", "rio de janeiro"):
            return "Outra cidade (%s)" % sig[:2].upper(), sig[:2].upper()
    return None


def _url_util(url):
    """Só o caminho/consulta da URL (o domínio pode ter nome de cidade, ex.: imobiliariacanoas.com.br)."""
    u = re.sub(r"^https?://[^/]+", "", url or "")
    return u


def detectar(url=None, titulo=None, endereco=None, descricao=None, html=None,
             latitude=None, longitude=None):
    for fonte, txt in (("url", _url_util(url)), ("titulo", titulo), ("endereco", endereco)):
        if txt:
            r = _achar(txt, rs_generico=(fonte == "url"))
            if r:
                return r[0], r[1], fonte
    if latitude and longitude:
        try:
            la, lo = float(latitude), float(longitude)
            if -30.27 < la < -29.93 and -51.31 < lo < -51.05:
                return POA, "RS", "coordenadas"
        except (TypeError, ValueError):
            pass
    r = _da_pagina(html)
    if r:
        return r[0], r[1], "pagina"
    if descricao:
        r = _achar(descricao, permite_uf=False, estrito=True)
        if r:
            return r[0], r[1], "descricao"
    return POA, "RS", "presumida"


def no_rs(uf):
    return (uf or "RS") == "RS"
