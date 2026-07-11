# 📡 Radar de Captação — Boletto Imóveis

Robô que monitora diariamente ~30 sites de imobiliárias de Porto Alegre **fora da Rede
Gaúcha de Imóveis** e detecta **imóveis novos** cadastrados nos bairros-alvo (Boa Vista,
Bela Vista, Auxiliadora, Três Figueiras, Chácara das Pedras, Jardim Europa, Passo da
Areia, Mont Serrat, Moinhos de Vento, Rio Branco, Independência, Santa Cecília, Vila
Jardim, Higienópolis, Petrópolis). Os achados aparecem num painel web com foto, preço,
bairro e link do anúncio — sua equipe entra em contato com o proprietário e capta.

Roda de graça na nuvem via **GitHub Actions** (2x ao dia: 7h e 14h de Brasília) e publica
o painel via **GitHub Pages**. Seu computador não precisa estar ligado.

## Como colocar no ar (uma única vez, ~15 minutos)

1. **Crie uma conta** em https://github.com (gratuita).
2. **Crie um repositório**: botão "+" → *New repository* → nome ex.: `radar-poa` →
   marque **Public** (o Pages gratuito exige repositório público — veja "Privacidade" abaixo)
   → *Create repository*.
3. **Suba os arquivos**: na página do repositório → *uploading an existing file* →
   arraste TODO o conteúdo desta pasta (incluindo as pastas `config`, `monitor`, `site`,
   `.github` — no Windows, ative "itens ocultos" para vê-la) → *Commit changes*.
   - Alternativa mais fácil: instale o [GitHub Desktop](https://desktop.github.com),
     clone o repositório vazio, copie os arquivos para dentro e clique em *Commit* → *Push*.
4. **Ative o Actions**: aba *Actions* → se aparecer um aviso, clique em
   *I understand my workflows, enable them*.
5. **Rode a primeira vez**: aba *Actions* → workflow "Radar de Captação" →
   *Run workflow*. Essa primeira execução só registra o estoque atual de cada site
   (linha de base) — os alertas de "imóvel novo" começam da segunda execução em diante.
6. **Ative o painel**: *Settings* → *Pages* → em *Branch* escolha `main` e pasta `/docs`
   → *Save*. Em ~2 minutos o painel estará em
   `https://SEU-USUARIO.github.io/radar-poa/`. Salve nos favoritos do celular.

Pronto. A partir daí tudo roda sozinho, 2x por dia.

## Ligar a locação (fase 2)

Edite `config/sites.json` e mude:
```json
"monitorar": { "venda": true, "locacao": true }
```

## Ajustes comuns

- **Adicionar/remover imobiliária**: edite a lista `sites` em `config/sites.json`
  (basta `id`, `nome`, `base` e `enabled: true`).
- **Adicionar bairro**: acrescente em `bairros_alvo` (inclua a versão com hífen e a
  versão com espaço/acento).
- **Receber tudo de POA** (sem filtro de bairro): `"somente_bairros_alvo": false`.
- **Horários**: edite os `cron` em `.github/workflows/monitor.yml` (horário UTC = Brasília +3).

## Como funciona

1. Para cada site, o robô lê o `sitemap.xml` (ou, na falta dele, as páginas de listagem)
   e coleta as URLs de anúncios individuais.
2. Compara com o que já conhecia (`data/known_urls.json`). URL nova = imóvel novo.
3. Busca a página do anúncio e extrai título, foto, preço e bairro.
4. Grava em `data/listings.json` e regenera o painel em `docs/`.

## Painel de saúde

No fim do painel há uma tabela mostrando o status de cada site na última execução.
Sites com "erro" recorrente podem ter mudado de estrutura ou bloqueado robôs — me avise
no Claude que eu ajusto a configuração daquele site.

## Privacidade

Repositório público = qualquer pessoa com o link consegue ver o painel. O nome do
repositório não é divulgado em lugar nenhum, mas se quiser sigilo total: (a) assine o
GitHub Pro (~US$ 4/mês) e torne o repositório privado com Pages privado, ou (b) desative
o Pages e baixe o arquivo `docs/index.html` + `docs/data.js` para abrir localmente.

## Boas práticas e limites

- O robô respeita intervalos entre requisições e roda só 2x/dia — carga mínima nos sites.
- Sites com forte proteção anti-robô (QuintoAndar, Lopes nacional) vêm desativados;
  monitore-os manualmente ou via portais.
- Ao captar, confira se o imóvel não está sob **contrato de exclusividade** vigente com
  a outra imobiliária.

## Cruzamento com a base Jetimob e com a RGI (status de cada imóvel)

Cada imóvel detectado recebe um status no painel:

- 🟢 **LIVRE** — não encontrado na sua base nem no portal da RGI: pode ir atrás.
- 🟡 **VERIFICAR** — características muito parecidas com um imóvel da base (mesmo
  bairro/área/dormitórios/preço): confira antes de investir tempo.
- 🔴 **CAPTADO** — já consta na sua base ou no portal da RGI (mostra a fonte e a
  referência). O status é reavaliado a cada execução, então um imóvel que era LIVRE
  muda para CAPTADO automaticamente quando entrar na base — é o aviso de "já foi".

O robô monta a "base conhecida" a partir de até 4 fontes (usa as que estiverem disponíveis):

1. **Feed XML do Jetimob (recomendado)** — no Jetimob: *Configurações → Integrações /
   Portais → adicionar integração* (pode ser um portal genérico/XML) e copie a URL do
   feed gerado. No GitHub: *Settings → Secrets and variables → Actions → New repository
   secret* → nome `JETIMOB_FEED_URL`, valor = a URL do feed. É a fonte mais precisa
   (bairro, área, dormitórios e preço estruturados). A URL fica em secret, não aparece
   no repositório público.
2. **Export CSV manual** — exporte os imóveis do Jetimob e salve como
   `data/meus_imoveis.csv` com colunas:
   `referencia,endereco,bairro,tipo,area,dormitorios,preco`. Atualize quando quiser.
3. **Site público da Boletto** (bolettoimoveis.com.br) — lido automaticamente.
4. **Portal da RGI** (redegauchadeimoveis.com.br) — lido automaticamente via sitemap;
   cobre o estoque de TODAS as associadas, evitando disputar imóvel que outra associada
   da rede já tem.

As fontes 3 e 4 são enriquecidas aos poucos (150 páginas por execução, com cache) —
nos primeiros dias o cruzamento com o portal RGI fica mais completo a cada rodada.

**Importante:** o robô NÃO usa seu login/senha do Jetimob (nem deve — senha em robô é
risco de segurança). O feed XML é o mecanismo oficial do Jetimob para expor o estoque.

## Alertas no WhatsApp

O robô manda mensagem no seu WhatsApp quando: 🟢 surge imóvel novo LIVRE para captar,
🔴 um anúncio da concorrência sai do ar (vendido ou perdeu o contrato — bom momento
para contatar o proprietário) e 💸 quando um anúncio monitorado tem queda de preço
(sinal de pressa do proprietário).

### Configurar (grátis, ~2 min por pessoa) — CallMeBot

1. No celular que vai receber os avisos, adicione o número do bot do CallMeBot aos
   contatos e envie a ele a mensagem `I allow callmebot to send me messages`
   (o número atual do bot está em https://www.callmebot.com/blog/free-api-whatsapp-messages/).
2. O bot responde com a sua **apikey**.
3. No GitHub: *Settings → Secrets and variables → Actions → New repository secret*
   - Nome: `WHATSAPP_DESTINOS`
   - Valor: `5551999998888:SUAAPIKEY` (número internacional sem "+"). Para mais pessoas,
     separe por vírgula: `5551999998888:key1,5551977776666:key2`.
4. (Opcional) Secret `PAINEL_URL` com o link do painel para constar nas mensagens.

Observações: o CallMeBot é um serviço gratuito de terceiros — as mensagens contêm apenas
links públicos de anúncios, nenhum dado de cliente. Para uso mais robusto/em escala, o
caminho oficial é a **WhatsApp Cloud API da Meta** (secrets `WA_META_TOKEN`,
`WA_META_PHONE_ID` e `WA_META_DESTINOS`) — exige conta Meta Business, mas é o canal
oficial. Evite gateways não oficiais (Baileys/Evolution etc.): violam os termos do
WhatsApp e arriscam banir o número da imobiliária.

## Novos recursos do painel (v3)

- ⚫ **REMOVIDO** — anúncio sumiu do site da concorrente em 2 execuções seguidas
  (filtro próprio no painel). Vendido ou contrato perdido: vale ligar.
- 💸 **PREÇO ↓** — queda ≥3% detectada na revisita (até 60 anúncios reverificados por
  execução, começando pelos mais antigos).
- ⏳ **90d+ no ar** — imóvel parado há mais de 90 dias na concorrente: proprietário
  provavelmente frustrado, ótimo alvo de captação.
  (O "tempo no ar" conta a partir da detecção pelo radar.)

## v5 — Localização, prioridade e fila de captação

Cada anúncio é classificado pelo nível de localização que o site "deixou vazar":

- 🎯 **P1 — endereço completo** (rua+número OU coordenada exata embutida no mapa da
  página): casas/terrenos P1 vão direto para pesquisa no eemovel.
- 📍 **P2 — prédio identificado** (rua + nome do edifício/condomínio): localizável em
  segundos; falta só a unidade.
- **P3 — só rua** · **P4 — só bairro**.

O extrator captura: nome do empreendimento, número, **latitude/longitude escondida no
código da página** (muitos sites embutem o pin do mapa mesmo sem mostrar o número — o
painel gera link "ver ponto exato" no Google Maps), tipo do imóvel e nível de endereço.
A tabela de saúde ganhou a coluna **"% endereço localizável" por imobiliária** — em uma
semana você saberá exatamente quais sites liberam localização.

### Fila de captação (no próprio painel)

Cada card tem: status de gestão (⬜ novo → 📞 contatado → 🤝 negociando → ✅ captado por
nós / 🗑 descartado), campo para o telefone do proprietário (obtido no eemovel) e botão
**"Abrir WhatsApp com script"** — abre o WhatsApp do corretor com mensagem personalizada
citando o imóvel e o endereço (edite o texto na função `scriptDe` em `site/build_site.py`).
O filtro "Gestão" mostra só os novos, só os em negociação etc. O CSV exporta tudo,
incluindo status e telefones.

⚠️ O status/telefones ficam salvos no navegador de cada corretor (localStorage) — não
sincronizam entre computadores. Para equipe grande, o passo seguinte é uma planilha
compartilhada ou CRM.

### Rotina diária sugerida (40 créditos eemovel)

1. Alerta do WhatsApp chega → abrir painel → filtro 🎯 P1 + 🟢 LIVRE + "Hoje/7 dias".
2. Pesquisar os P1 no eemovel (casas de rua primeiro), colar telefone no card.
3. Sobrou crédito? P2: localizar o prédio pelo nome + "ver ponto exato".
4. Contatar via botão WhatsApp ou ligação; atualizar o status no card.

### Sobre automação total do contato (WhatsApp API / IA de voz)

- **WhatsApp oficial (Meta Cloud API)**: exige conta Meta Business, número dedicado e
  template de mensagem pré-aprovado. Custo por conversa de marketing (~R$ 0,30-0,60).
  Disparo de mensagem fora da API oficial (número comum + automação) leva a banimento.
- **IA de voz** (Vapi, Retell, Zenvia Voice etc.): ~R$ 1-3/minuto; funciona para
  pré-qualificar ("o imóvel ainda está disponível? aceita conversar com outra
  imobiliária?") e transferir os interessados para o corretor.
- **LGPD**: telefone de proprietário obtido via eemovel = dado pessoal. Use base de
  interesse legítimo, identifique-se sempre, ofereça opt-out ("não quer mais contato?")
  e registre os descartes. Com 20-30 contatos/dia personalizados o risco é baixo;
  disparo em massa genérico é o que gera denúncia.

## Auditoria de endereços (quem deixa o número vazar)

Algumas imobiliárias publicam rua+número sem perceber (confirmado em MultiImob e
Private) e replicam isso em portais. Para mapear TODA a lista de uma vez:
aba *Actions* → **"Auditoria de endereços"** → *Run workflow*. O robô amostra 10
anúncios de cada um dos 30 sites e gera um ranking (`docs/auditoria.csv` + tabela no
log) com: % com número, % com coordenada exata embutida, % com nome do prédio.
Use o ranking para priorizar quais sites merecem monitoramento mais frequente —
e repita a auditoria a cada 2-3 meses, pois os sites mudam.
