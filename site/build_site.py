#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o painel estático (docs/) a partir de data/*.json — v4 com ficha completa e filtros."""
import json, os, re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

def load(p, d):
    fp = os.path.join(DATA, p)
    return json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else d

listings = load("listings.json", [])
runlog = load("runlog.json", {"executado_em": None, "sites": {}})

def _num(preco):
    if isinstance(preco, (int, float)):
        return preco
    m = re.search(r"[\d\.]{4,}(?:,\d{2})?", str(preco or ""))
    return float(m.group(0).replace(".", "").replace(",", ".")) if m else None

for l in listings:
    l["preco_num"] = l.get("preco_venda") or _num(l.get("preco"))
    l["area_num"] = l.get("area")
listings.sort(key=lambda l: (l.get("detectado_em") or ""), reverse=True)

with open(os.path.join(DOCS, "data.js"), "w", encoding="utf-8") as f:
    f.write("const LISTINGS = ")
    json.dump(listings, f, ensure_ascii=False)
    f.write(";\nconst RUNLOG = ")
    json.dump(runlog, f, ensure_ascii=False)
    f.write(";\nconst GERADO_EM = " + json.dumps(datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")) + ";")

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Radar de Captação — Boletto Imóveis</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1a2230;--mut:#6b7686;--acc:#0f4c81;--new:#e8f5ee;--newb:#1c7c4e}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--acc);color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
header h1{font-size:18px;margin:0}header small{opacity:.8}
.wrap{max-width:1240px;margin:0 auto;padding:16px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;align-items:center}
.filters select,.filters input{padding:8px 10px;border:1px solid #d5dae2;border-radius:8px;font-size:13px;background:#fff}
.filters input[type=text]{flex:1;min-width:170px}
.filters input.mini{width:96px}
.chips{display:flex;gap:6px}.chip{padding:7px 12px;border-radius:999px;border:1px solid #d5dae2;background:#fff;cursor:pointer;font-size:13px}
.chip.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.btn{padding:8px 14px;border-radius:8px;border:1px solid var(--acc);background:#fff;color:var(--acc);cursor:pointer;font-size:13px;font-weight:600}
.stats{font-size:13px;color:var(--mut);margin:6px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.card{background:var(--card);border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);display:flex;flex-direction:column}
.card img{width:100%;height:160px;object-fit:cover;background:#e2e6ec}
.card .noimg{width:100%;height:160px;background:linear-gradient(135deg,#dde3ec,#c6cfdc);display:flex;align-items:center;justify-content:center;color:#8a94a6;font-size:34px}
.card .body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:6px;flex:1}
.card .t{font-size:14px;font-weight:600;line-height:1.3;max-height:3.9em;overflow:hidden}
.badges{display:flex;gap:5px;flex-wrap:wrap}
.b{font-size:11px;padding:2px 8px;border-radius:999px;background:#eef1f5;color:#42506a}
.b.new{background:var(--new);color:var(--newb);font-weight:700}
.b.tipo{background:#fdf1e3;color:#8a5a1a}
.b.st-livre{background:#e8f5ee;color:#1c7c4e;font-weight:700}.b.st-ver{background:#fff8e0;color:#8a6d00;font-weight:700}
.b.st-cap{background:#fdecea;color:#b3261e;font-weight:700}.b.st-rem{background:#e8e8e8;color:#444;font-weight:700}
.b.st-queda{background:#e7f0fd;color:#1b4fa0;font-weight:700}
.specs{font-size:12.5px;color:#33415c;font-weight:600}
.custos{font-size:12px;color:var(--mut)}
.preco{font-size:15px;font-weight:700;color:var(--acc)}
.preco small{color:var(--mut);font-weight:400}
.src{font-size:12px;color:var(--mut)}
.comp{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--mut)}
.comp .bar{flex:1;height:5px;border-radius:4px;background:#e8ecf2;overflow:hidden}
.comp .bar i{display:block;height:100%;background:#1c7c4e}
.comp.low .bar i{background:#d4a017}
.carac{font-size:11px;color:#5a6a85;max-height:2.6em;overflow:hidden}
.gestao{display:flex;flex-direction:column;gap:5px;border-top:1px dashed #e2e6ec;padding-top:7px}
.gestao select,.gestao input{padding:6px 8px;border:1px solid #d5dae2;border-radius:7px;font-size:12px}
.gestao a.wa{text-align:center;padding:7px;border-radius:7px;background:#25d366;color:#fff;text-decoration:none;font-size:12.5px;font-weight:700}
.card a.go{margin-top:auto;text-align:center;padding:8px;border-radius:8px;background:var(--acc);color:#fff;text-decoration:none;font-size:13px;font-weight:600}
.health{margin-top:26px;background:#fff;border-radius:12px;padding:14px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.health h2{font-size:15px;margin:0 0 10px}
.health table{width:100%;border-collapse:collapse;font-size:13px}
.health td,.health th{padding:5px 8px;border-bottom:1px solid #eef1f5;text-align:left}
.ok{color:#1c7c4e}.err{color:#b3261e}.base{color:#8a5a1a}
.empty{padding:50px;text-align:center;color:var(--mut)}
</style>
</head>
<body>
<header><h1>📡 Radar de Captação — imóveis novos fora da RGI</h1>
<div><a href="dashboard.html" style="color:#fff;font-size:13px;font-weight:700;text-decoration:none;background:rgba(255,255,255,.15);padding:7px 14px;border-radius:8px">📊 Dashboard</a>
<small id="gen" style="margin-left:10px"></small></div></header>
<div class="wrap">
  <div class="filters">
    <input type="text" id="q" placeholder="Buscar título, endereço, característica (ex.: churrasqueira)...">
    <select id="fimob"><option value="">Todas as imobiliárias</option></select>
    <select id="fbairro"><option value="">Todos os bairros</option></select>
    <select id="ftipo"><option value="">Venda + Locação</option><option value="venda">Venda</option><option value="locacao">Locação</option></select>
    <select id="fstatus"><option value="">Todos os status</option><option value="livre">🟢 Livres p/ captar</option><option value="verificar">🟡 Verificar</option><option value="captado">🔴 Já captados</option><option value="removido">⚫ Removidos</option></select>
    <div class="chips">
      <button class="chip on" data-d="1">Hoje</button>
      <button class="chip" data-d="7">7 dias</button>
      <button class="chip" data-d="30">30 dias</button>
      <button class="chip" data-d="0">Tudo</button>
    </div>
  </div>
  <div class="filters">
    <select id="fdorm"><option value="">Dorm. (qualquer)</option><option>1</option><option>2</option><option>3</option><option>4</option></select>
    <select id="fsuite"><option value="">Suítes (qualquer)</option><option>1</option><option>2</option><option>3</option></select>
    <select id="fvaga"><option value="">Vagas (qualquer)</option><option>1</option><option>2</option><option>3</option></select>
    <input class="mini" type="number" id="pmin" placeholder="R$ mín (mil)">
    <input class="mini" type="number" id="pmax" placeholder="R$ máx (mil)">
    <input class="mini" type="number" id="amin" placeholder="m² mín">
    <input class="mini" type="number" id="amax" placeholder="m² máx">
    <select id="fcomp"><option value="">Ficha (qualquer)</option><option value="70">Completa (70%+)</option><option value="40">Média (40%+)</option><option value="-40">Incompleta (&lt;40%)</option></select>
    <select id="fprio"><option value="">Prioridade (todas)</option><option value="1">🎯 P1 — endereço completo</option><option value="2">📍 P2 — prédio identificado</option><option value="3">P3 — só rua</option><option value="4">P4 — só bairro</option></select>
    <select id="fgestao"><option value="">Gestão (todos)</option><option value="novo">Novos (sem contato)</option><option value="contatado">Contatados</option><option value="negociando">Negociando</option><option value="captado_nosso">Captados por nós ✅</option><option value="descartado">Descartados</option></select>
    <button class="btn" id="csv">⬇ Exportar CSV</button>
  </div>
  <div class="stats" id="stats"></div>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" style="display:none">Nenhum imóvel com esses filtros.<br>A primeira execução apenas registra o estoque (linha de base); os alertas começam na segunda.</div>
  <div class="health"><h2>Saúde do monitoramento (última execução)</h2><table id="health"></table></div>
</div>
<script src="data.js"></script>
<script>
const $=s=>document.querySelector(s);
$('#gen').textContent='Atualizado: '+GERADO_EM;
let days=1, filtradas=[];
const uniq=a=>[...new Set(a.filter(Boolean))].sort();
uniq(LISTINGS.map(l=>l.imobiliaria)).forEach(v=>fimob.add(new Option(v,v)));
uniq(LISTINGS.map(l=>l.bairro)).forEach(v=>fbairro.add(new Option(v,v)));
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));c.classList.add('on');days=+c.dataset.d;render()});
['q','fimob','fbairro','ftipo','fstatus','fdorm','fsuite','fvaga','pmin','pmax','amin','amax','fcomp','fprio','fgestao'].forEach(id=>document.getElementById(id).oninput=render);
const daysAgo=d=>(Date.now()-new Date(d+'T00:00:00Z'))/864e5;
const GEST=JSON.parse(localStorage.getItem('radar_gestao')||'{}');
window.gDe=u=>GEST[u]||{st:'novo',tel:'',obs:''};
window.setG=(u,k,v)=>{const g=gDe(u);g[k]=v;GEST[u]=g;localStorage.setItem('radar_gestao',JSON.stringify(GEST));if(k==='st'||k==='tel')render();};
window.scriptDe=l=>`Olá! Tudo bem? Sou da Boletto Imóveis, aqui de Porto Alegre. Vi que o imóvel ${l.titulo||''}${l.endereco?' na '+l.endereco:l.bairro?' no bairro '+l.bairro:''} está à venda. Trabalhamos com a Rede Gaúcha de Imóveis (60+ imobiliárias vendendo juntas) e temos clientes buscando nessa região. Posso te apresentar nossa proposta de divulgação, sem exclusividade obrigatória?`;
function passa(l){
  const q=$('#q').value.toLowerCase(), st=fstatus.value, comp=fcomp.value;
  if(fimob.value&&l.imobiliaria!==fimob.value)return false;
  if(fbairro.value&&l.bairro!==fbairro.value)return false;
  if(ftipo.value&&l.tipo!==ftipo.value)return false;
  if(st){if(st==='removido'){if(!l.removido_em)return false}else{if((l.status||'livre')!==st||l.removido_em)return false}}
  if(days!==0&&daysAgo(l.detectado_em)>days)return false;
  if(fdorm.value&&!((l.dorms||0)>=+fdorm.value))return false;
  if(fsuite.value&&!((l.suites||0)>=+fsuite.value))return false;
  if(fvaga.value&&!((l.vagas||0)>=+fvaga.value))return false;
  if(pmin.value&&!(l.preco_num&&l.preco_num>=+pmin.value*1000))return false;
  if(pmax.value&&!(l.preco_num&&l.preco_num<=+pmax.value*1000))return false;
  if(amin.value&&!(l.area_num&&l.area_num>=+amin.value))return false;
  if(amax.value&&!(l.area_num&&l.area_num<=+amax.value))return false;
  if(comp){const c=l.completude||0;if(comp==='-40'){if(c>=40)return false}else if(c<+comp)return false}
  if(fprio.value&&String(l.prioridade||4)!==fprio.value)return false;
  if(fgestao.value&&gDe(l.url).st!==fgestao.value)return false;
  if(q){const blob=((l.titulo||'')+' '+(l.bairro||'')+' '+(l.endereco||'')+' '+(l.descricao||'')+' '+((l.caracteristicas||[]).join(' '))+' '+l.url).toLowerCase();if(!blob.includes(q))return false}
  return true;
}
function specsDe(l){
  return [l.dorms?l.dorms+' dorm':null,l.suites?l.suites+' suíte'+(l.suites>1?'s':''):null,
          l.vagas?l.vagas+' vaga'+(l.vagas>1?'s':''):null,l.banheiros?l.banheiros+' banh.':null,
          l.area?Math.round(l.area)+' m²':null].filter(Boolean).join(' · ');
}
function render(){
  filtradas=LISTINGS.filter(passa);
  $('#stats').textContent=filtradas.length+' imóvel(is) · acumulado total: '+LISTINGS.length;
  $('#grid').innerHTML=filtradas.map(l=>{
    const hoje=daysAgo(l.detectado_em)<=1, comp=l.completude||0;
    const custos=[l.condominio_fmt?'Cond. '+l.condominio_fmt:null,l.iptu_fmt?'IPTU '+l.iptu_fmt:null].filter(Boolean).join(' · ');
    return `<div class="card">
      ${l.foto?`<img loading="lazy" src="${l.foto}" onerror="this.outerHTML='<div class=noimg>🏠</div>'">`:'<div class="noimg">🏠</div>'}
      <div class="body">
        <div class="badges">
          ${hoje&&!l.removido_em&&l.origem!=='garimpo'?'<span class="b new">NOVO HOJE</span>':''}
          ${l.origem==='garimpo'?'<span class="b">🗄 estoque</span>':''}
          ${l.removido_em?'<span class="b st-rem">⚫ REMOVIDO</span>':''}
          ${l.queda?'<span class="b st-queda">💸 PREÇO ↓</span>':''}
          ${daysAgo(l.detectado_em)>=90&&!l.removido_em?'<span class="b">⏳ 90d+</span>':''}
          ${{'livre':'<span class="b st-livre">🟢 LIVRE</span>','verificar':'<span class="b st-ver">🟡 VERIFICAR</span>','captado':'<span class="b st-cap">🔴 CAPTADO</span>'}[l.status||'livre']}
          <span class="b tipo">${l.tipo==='locacao'?'Locação':l.tipo==='venda'?'Venda':'—'}</span>
          ${l.bairro?`<span class="b">${l.bairro}</span>`:''}
          ${l.prioridade===1?'<span class="b st-livre">🎯 P1 EEMOVEL</span>':l.prioridade===2?'<span class="b st-queda">📍 P2 PRÉDIO</span>':''}
        </div>
        <div class="t">${l.titulo||l.url.split('/').slice(-1)[0].replace(/-/g,' ')}</div>
        ${specsDe(l)?`<div class="specs">${specsDe(l)}</div>`:''}
        <div class="preco">${l.preco||'—'}${l.preco_locacao_fmt?` <small>· aluguel ${l.preco_locacao_fmt}</small>`:''}</div>
        ${custos?`<div class="custos">${custos}</div>`:''}
        ${l.caracteristicas&&l.caracteristicas.length?`<div class="carac">✦ ${l.caracteristicas.join(', ')}</div>`:''}
        ${l.endereco||l.empreendimento?`<div class="custos">📍 ${[l.empreendimento,l.endereco].filter(Boolean).join(' — ')}${l.latitude?` · <a href="https://www.google.com/maps?q=${l.latitude},${l.longitude}" target="_blank" rel="noopener">ver ponto exato 🗺</a>`:''}</div>`:l.latitude?`<div class="custos">🗺 <a href="https://www.google.com/maps?q=${l.latitude},${l.longitude}" target="_blank" rel="noopener">ponto exato no mapa</a></div>`:''}
        <div class="comp ${comp<40?'low':''}"><span>Ficha ${comp}%</span><div class="bar"><i style="width:${comp}%"></i></div>${l.codigo?`<span>ref ${l.codigo}</span>`:''}</div>
        <div class="src">${l.imobiliaria} · detectado ${l.detectado_em.split('-').reverse().join('/')} · no ar há ${Math.max(1,Math.round(daysAgo(l.detectado_em)))}d${l.status==='captado'&&l.match_fonte?` · na base: ${l.match_fonte==='portal_rgi'?'portal RGI':l.match_fonte}${l.match_ref?' (ref '+l.match_ref+')':''}`:''}</div>
        <div class="gestao">
          <select onchange="setG('${l.url}','st',this.value)">${['novo','contatado','negociando','captado_nosso','descartado'].map(s=>`<option value="${s}" ${gDe(l.url).st===s?'selected':''}>${{novo:'⬜ novo',contatado:'📞 contatado',negociando:'🤝 negociando',captado_nosso:'✅ captado por nós',descartado:'🗑 descartado'}[s]}</option>`).join('')}</select>
          <input placeholder="Tel. proprietário" value="${gDe(l.url).tel||''}" onchange="setG('${l.url}','tel',this.value)">
          ${gDe(l.url).tel?`<a class="wa" target="_blank" rel="noopener" href="https://wa.me/55${gDe(l.url).tel.replace(/\D/g,'')}?text=${encodeURIComponent(scriptDe(l))}">💬 Abrir WhatsApp c/ script</a>`:''}
        </div>
        <a class="go" href="${l.url}" target="_blank" rel="noopener">Ver anúncio ↗</a>
      </div></div>`}).join('');
  $('#empty').style.display=filtradas.length?'none':'block';
}
$('#csv').onclick=()=>{
  const cols=['status','prioridade','endereco_nivel','tipo','tipo_imovel','bairro','titulo','dorms','suites','vagas','banheiros','area','preco_num','preco_locacao','condominio','iptu','empreendimento','endereco','numero','latitude','longitude','codigo','completude','imobiliaria','detectado_em','removido_em','url','gestao_status','gestao_tel','gestao_obs'];
  const esc=v=>'"'+String(v==null?'':Array.isArray(v)?v.join('; '):v).replace(/"/g,'""')+'"';
  const csv=[cols.join(';')].concat(filtradas.map(l=>{const g=gDe(l.url);const r={...l,gestao_status:g.st,gestao_tel:g.tel,gestao_obs:g.obs};return cols.map(c=>esc(r[c])).join(';')})).join('\\r\\n');
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob(['\\ufeff'+csv],{type:'text/csv;charset=utf-8'}));
  a.download='radar_captacao.csv';a.click();
};
const END={};LISTINGS.forEach(l=>{const k=l.imobiliaria;END[k]=END[k]||{t:0,c:0};END[k].t++;if(['completo','rua+condominio'].includes(l.endereco_nivel))END[k].c++;});
const pctEnd=n=>{const e=END[n];return e&&e.t?Math.round(100*e.c/e.t)+'%':'—'};
const H=$('#health');
H.innerHTML='<tr><th>Imobiliária</th><th>Status</th><th>Método</th><th>URLs de imóvel</th><th>Novos</th><th>% endereço localizável</th></tr>'+
 Object.values(RUNLOG.sites||{}).map(s=>`<tr><td>${s.nome}</td>
 <td class="${s.status==='ok'?'ok':s.status==='erro'?'err':'base'}">${s.status}${s.erro?' — '+s.erro:''}</td>
 <td>${s.metodo||'—'}</td><td>${s.urls_imovel??'—'}</td><td>${s.novos??0}</td><td>${pctEnd(s.nome)}</td></tr>`).join('');
render();
</script>
</body>
</html>"""

with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
    f.write(HTML)

# ================= DASHBOARD ANALÍTICO =================
from collections import Counter, defaultdict
known = load("known_urls.json", {})
hoje_dt = datetime.now(timezone.utc).date()

def dias_no_ar(l):
    try:
        d = datetime.strptime(l["detectado_em"], "%Y-%m-%d").date()
        fim = datetime.strptime(l["removido_em"], "%Y-%m-%d").date() if l.get("removido_em") else hoje_dt
        return max(0, (fim - d).days)
    except Exception:
        return 0

ativos = [l for l in listings if not l.get("removido_em")]
livres = [l for l in ativos if l.get("status", "livre") == "livre"]

S = {}
S["visao"] = {
    "vigiados": sum(len(v) for v in known.values()),
    "oportunidades": len(ativos),
    "livres": len(livres),
    "verificar": sum(1 for l in ativos if l.get("status") == "verificar"),
    "captados_rede": sum(1 for l in ativos if l.get("status") == "captado"),
    "removidos": len(listings) - len(ativos),
    "quedas": sum(1 for l in listings if l.get("queda")),
    "p1_livres": sum(1 for l in livres if l.get("prioridade") == 1),
}
S["por_status"] = dict(Counter((l.get("status") or "livre") for l in ativos))
S["por_prioridade"] = dict(Counter("P%d" % (l.get("prioridade") or 4) for l in livres))
S["por_bairro"] = dict(Counter(l["bairro"] for l in livres if l.get("bairro")).most_common(15))
S["por_tipo"] = dict(Counter(l.get("tipo_imovel") or "n/ident." for l in livres).most_common(8))
S["por_dorms"] = dict(sorted(Counter(str(l["dorms"]) for l in livres if l.get("dorms")).items()))

faixas = [
    ("até 400k",        0,        400_001),
    ("401-650k",        400_001,  650_001),
    ("651k-1M",         650_001,  1_000_001),
    ("1M-1,5M",         1_000_001, 1_500_001),
    ("1,5M-2M",         1_500_001, 2_000_001),
    ("2M-2,5M",         2_000_001, 2_500_001),
    ("2,5M-3M",         2_500_001, 3_000_001),
    ("3M-5M",           3_000_001, 5_000_001),
    ("5M-7M",           5_000_001, 7_000_001),
    ("7M-10M",          7_000_001, 10_000_001),
    ("10M-15M",         10_000_001, 15_000_001),
    ("15M-20M",         15_000_001, 20_000_001),
    ("20M+",            20_000_001, 1e15),
]
S["por_preco"] = {n: sum(1 for l in livres if l.get("preco_num") and lo <= l["preco_num"] < hi) for n,lo,hi in faixas}

# preço médio do m² por bairro (venda, com área plausível)
pm2 = defaultdict(list)
for l in ativos:
    if l.get("tipo") != "locacao" and l.get("preco_num") and l.get("area_num") and 20 <= l["area_num"] <= 2000:
        v = l["preco_num"] / l["area_num"]
        if 2000 <= v <= 60000 and l.get("bairro"):
            pm2[l["bairro"]].append(v)
S["preco_m2"] = {b: round(sum(v)/len(v)) for b, v in sorted(pm2.items(), key=lambda kv: -len(kv[1]))[:12] if len(v) >= 3}

# tempo de estoque
buckets = [("0-30d",0,30),("31-60d",31,60),("61-90d",61,90),("90d+",91,99999)]
S["estoque_tempo"] = {n: sum(1 for l in ativos if lo <= dias_no_ar(l) <= hi) for n,lo,hi in buckets}

# detecções por dia (últimos 30)
por_dia = Counter(l["detectado_em"] for l in listings if l.get("origem") != "garimpo")
dias_ord = sorted(por_dia)[-30:]
S["timeline"] = {"labels": [d[5:].replace("-", "/") for d in dias_ord], "valores": [por_dia[d] for d in dias_ord]}

# por imobiliária: oportunidades, % endereço, completude média, estoque vigiado
imobs = {}
for l in ativos:
    k = l["imobiliaria"]
    e = imobs.setdefault(k, {"ops": 0, "livres": 0, "end": 0, "comp": [], "dias": []})
    e["ops"] += 1
    e["livres"] += 1 if l.get("status", "livre") == "livre" else 0
    e["end"] += 1 if (l.get("endereco_nivel") in ("completo", "rua+condominio")) else 0
    if l.get("completude"): e["comp"].append(l["completude"])
    e["dias"].append(dias_no_ar(l))
sid2nome = {}
for l in listings: sid2nome[l["site_id"]] = l["imobiliaria"]
S["imobiliarias"] = [{
    "nome": k, "ops": v["ops"], "livres": v["livres"],
    "pct_end": round(100*v["end"]/v["ops"]) if v["ops"] else 0,
    "comp_media": round(sum(v["comp"])/len(v["comp"])) if v["comp"] else 0,
    "dias_medio": round(sum(v["dias"])/len(v["dias"])) if v["dias"] else 0,
    "vigiados": len(known.get(next((s for s,n in sid2nome.items() if n==k), ""), [])),
} for k, v in sorted(imobs.items(), key=lambda kv: -kv[1]["ops"])]

with open(os.path.join(DOCS, "dash_data.js"), "w", encoding="utf-8") as f:
    f.write("const STATS = "); json.dump(S, f, ensure_ascii=False)
    f.write(";\nconst DGERADO = " + json.dumps(datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")) + ";")

DASH = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Dashboard — Radar de Captação</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root{--acc:#0f4c81;--ink:#1a2230;--mut:#6b7686;--bg:#f5f6f8}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--acc);color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
header h1{font-size:18px;margin:0}
header a{color:#fff;font-size:13px;font-weight:700;text-decoration:none;background:rgba(255,255,255,.15);padding:7px 14px;border-radius:8px}
.wrap{max-width:1240px;margin:0 auto;padding:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:#fff;border-radius:12px;padding:14px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.kpi .v{font-size:30px;font-weight:800;color:var(--acc)}
.kpi.green .v{color:#1c7c4e}.kpi.red .v{color:#b3261e}
.kpi .l{font-size:12px;color:var(--mut);margin-top:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}
.box{background:#fff;border-radius:12px;padding:14px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.box h2{font-size:14px;margin:0 0 10px;color:var(--ink)}
.box canvas{max-height:260px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
td,th{padding:5px 7px;border-bottom:1px solid #eef1f5;text-align:left}
th{color:var(--mut);font-weight:600}
.funil{display:flex;gap:8px;flex-wrap:wrap}
.fstep{flex:1;min-width:120px;text-align:center;padding:12px 6px;border-radius:10px;background:#eef3fa}
.fstep b{display:block;font-size:24px;color:var(--acc)}
.fstep small{color:var(--mut)}
.note{font-size:11px;color:var(--mut);margin-top:6px}
</style>
</head>
<body>
<header><h1>📊 Dashboard — Radar de Captação</h1><div><a href="index.html">📡 Voltar ao painel</a> <small id="g" style="margin-left:8px"></small></div></header>
<div class="wrap">
  <div class="kpis" id="kpis"></div>
  <div class="box" style="margin-bottom:14px"><h2>Funil de captação (status de gestão deste navegador)</h2><div class="funil" id="funil"></div>
  <div class="note">O funil usa os status marcados nos cards por quem usa este navegador.</div></div>
  <div class="grid">
    <div class="box"><h2>Oportunidades livres por bairro</h2><canvas id="cBairro"></canvas></div>
    <div class="box"><h2>Preço médio do m² por bairro (anúncios monitorados)</h2><canvas id="cM2"></canvas></div>
    <div class="box"><h2>Tempo de estoque na concorrência</h2><canvas id="cTempo"></canvas></div>
    <div class="box"><h2>Detecções de imóveis novos por dia</h2><canvas id="cTime"></canvas></div>
    <div class="box"><h2>Livres por prioridade de endereço</h2><canvas id="cPrio"></canvas></div>
    <div class="box"><h2>Livres por tipo de imóvel</h2><canvas id="cTipo"></canvas></div>
    <div class="box"><h2>Livres por dormitórios</h2><canvas id="cDorm"></canvas></div>
    <div class="box"><h2>Livres por faixa de preço</h2><canvas id="cPreco"></canvas></div>
  </div>
  <div class="box" style="margin-top:14px"><h2>Raio-x por imobiliária</h2><table id="tImob"></table></div>
</div>
<script src="dash_data.js"></script>
<script>
document.getElementById('g').textContent='Atualizado: '+DGERADO;
const V=STATS.visao;
const kpis=[[V.vigiados.toLocaleString('pt-BR'),'imóveis vigiados',''],[V.oportunidades,'oportunidades no painel',''],
 [V.livres,'🟢 livres p/ captar','green'],[V.p1_livres,'🎯 P1 livres (eemovel)','green'],
 [V.verificar,'🟡 a verificar',''],[V.captados_rede,'🔴 já na base/RGI',''],
 [V.removidos,'⚫ saíram do ar','red'],[V.quedas,'💸 quedas de preço','']];
document.getElementById('kpis').innerHTML=kpis.map(k=>`<div class="kpi ${k[2]}"><div class="v">${k[0]}</div><div class="l">${k[1]}</div></div>`).join('');
// funil da gestão local
const GEST=JSON.parse(localStorage.getItem('radar_gestao')||'{}');
const fc={novo:0,contatado:0,negociando:0,captado_nosso:0,descartado:0};
fc.novo=V.livres;Object.values(GEST).forEach(g=>{if(fc[g.st]!==undefined&&g.st!=='novo'){fc[g.st]++;fc.novo=Math.max(0,fc.novo-1)}});
const fl=[['Livres (sem contato)',fc.novo],['📞 Contatados',fc.contatado],['🤝 Negociando',fc.negociando],['✅ Captados por nós',fc.captado_nosso],['🗑 Descartados',fc.descartado]];
document.getElementById('funil').innerHTML=fl.map(f=>`<div class="fstep"><b>${f[1]}</b><small>${f[0]}</small></div>`).join('');
const AZ='#0f4c81',PAL=['#0f4c81','#1c7c4e','#d4a017','#b3261e','#6b7686','#7c5cbf','#2a9d8f','#e76f51'];
const bar=(id,obj,cor,fmt)=>new Chart(document.getElementById(id),{type:'bar',
 data:{labels:Object.keys(obj),datasets:[{data:Object.values(obj),backgroundColor:cor||AZ}]},
 options:{plugins:{legend:{display:false}},scales:{x:{ticks:{font:{size:10}}},y:{beginAtZero:true,ticks:fmt?{callback:v=>fmt(v)}:{}}}}});
bar('cBairro',STATS.por_bairro);
bar('cM2',STATS.preco_m2,'#1c7c4e',v=>'R$ '+(v/1000).toFixed(0)+'k');
bar('cTempo',STATS.estoque_tempo,'#d4a017');
bar('cDorm',STATS.por_dorms);
bar('cPreco',STATS.por_preco,'#7c5cbf');
new Chart(document.getElementById('cPrio'),{type:'doughnut',data:{labels:Object.keys(STATS.por_prioridade),
 datasets:[{data:Object.values(STATS.por_prioridade),backgroundColor:['#1c7c4e','#0f4c81','#d4a017','#9aa6ba']}]},
 options:{plugins:{legend:{position:'right'}}}});
new Chart(document.getElementById('cTipo'),{type:'doughnut',data:{labels:Object.keys(STATS.por_tipo),
 datasets:[{data:Object.values(STATS.por_tipo),backgroundColor:PAL}]},options:{plugins:{legend:{position:'right'}}}});
new Chart(document.getElementById('cTime'),{type:'line',data:{labels:STATS.timeline.labels,
 datasets:[{data:STATS.timeline.valores,borderColor:AZ,backgroundColor:'rgba(15,76,129,.12)',fill:true,tension:.3}]},
 options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}}});
document.getElementById('tImob').innerHTML='<tr><th>Imobiliária</th><th>Estoque vigiado</th><th>Oportunidades</th><th>🟢 Livres</th><th>% endereço localizável</th><th>Ficha média</th><th>Tempo médio no ar</th></tr>'+
 STATS.imobiliarias.map(i=>`<tr><td>${i.nome}</td><td>${i.vigiados.toLocaleString('pt-BR')}</td><td>${i.ops}</td><td>${i.livres}</td><td>${i.pct_end}%</td><td>${i.comp_media}%</td><td>${i.dias_medio}d</td></tr>`).join('');
</script>
</body>
</html>"""
with open(os.path.join(DOCS, "dashboard.html"), "w", encoding="utf-8") as f:
    f.write(DASH)
print("painel + dashboard gerados em docs/ —", len(listings), "imóveis no acumulado")
