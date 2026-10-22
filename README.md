# Plantando Ideias — Árvores do Campus

Site do projeto de extensão do **IFSul Campus Passo Fundo**. Cada árvore plantada recebe uma placa com QR Code que leva a uma página pública, onde qualquer pessoa vê **quando a árvore foi regada pela última vez** e pode registrar uma rega na hora.

> **Status:** M1 a M4 concluídos: modelo e seed; página pública com selo e registro de rega; admin com chuva, QR e etiquetas; mapa público.
> Veja [Pendências](#pendências) para o que depende de informação externa.

| Atrasada | Regada agora | Aguardando plantio |
| :---: | :---: | :---: |
| ![Selo vermelho](docs/img/tree-red.png) | ![Rega registrada](docs/img/tree-watered.png) | ![Muda aguardando local](docs/img/tree-awaiting.png) |

---

## ⚠️ A `BASE_URL` é permanente

O QR de cada placa codifica `{BASE_URL}/a/{public_id}`. **Depois que as placas forem impressas, essa URL não pode mudar**, senão todas as placas viram links quebrados.

- Use um domínio próprio ou um subdomínio do IFSul (ex.: `arvores.passofundo.ifsul.edu.br`).
- **Não** use uma URL de hospedagem gratuita (`*.onrender.com`, `*.vercel.app`, IP do servidor etc.). Se trocar de hospedagem, o domínio vai junto.
- Se for inevitável trocar, mantenha o domínio antigo redirecionando (301) `/a/*` para o novo.
- O `public_id` (8 caracteres aleatórios) também é permanente. Nunca regere os IDs de árvores que já têm placa.

---

## Como rodar

Requisitos: Docker e Docker Compose.

```bash
cp .env.example .env
# edite .env: POSTGRES_PASSWORD, SECRET_KEY, IP_HASH_SALT, ADMIN_PASSWORD, BASE_URL, MAP_CENTER
docker compose up -d --build        # sobe o banco e a app; as migrations rodam no start
docker compose exec app python -m app.seed   # dados iniciais (pode rodar mais de uma vez)
```

App em http://localhost:8000, health check em `/health`.

### Testes

Os testes rodam contra um PostgreSQL real (não SQLite), usando as migrations do Alembic.

```bash
docker compose --profile test run --rm tests
```

Os testes cobrem as adaptações para a Vercel (URL do Neon, engine serverless, IP pelos cabeçalhos, fotos no Blob com SDK simulado), a regra do selo, o rate limit e o intervalo mínimo, a geração de QR (decodificada com zxing-cpp, conferindo URL e nível H), o PDF de etiquetas (lido com pypdf), a autenticação, as fotos (remoção de EXIF) e a validação de GeoJSON.

Fora do Docker (Python 3.12 e um Postgres local com o banco `arvores_test`):

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt -c requirements.lock
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/arvores_test pytest
```

### Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "descricao"   # revise o arquivo gerado antes de commitar
```

---

## Stack

Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy 2 (async, asyncpg) · Alembic · Pydantic v2 · HTML/CSS/JS vanilla (ES modules) · Leaflet · segno (QR) · reportlab (PDF) · pytest · Docker Compose.

As dependências diretas estão fixadas em `requirements.txt`. O conjunto completo resolvido para Python 3.12 está em `requirements.lock`, usado como constraint no build.

---

## Página pública da árvore (`/a/{public_id}`)

- Foto, nome popular e científico, código e idade ("plantada há 12 dias").
- **Selo de rega:** "Regada há 1 dia (ontem, 08:10)", em verde, amarelo, vermelho ou cinza. Tem sempre ícone e texto, nunca só a cor.
- **Botão "Reguei agora"**, com nome opcional. A resposta do servidor já traz o selo atualizado.
- Últimas regas, timeline de fotos, sobre a espécie (campos vazios aparecem como "informação em revisão"), origem e mini-mapa.
- Árvore aguardando plantio mostra só "Esta muda ainda aguarda o local de plantio", sem selo. Árvore morta mostra uma mensagem própria.
- Feita para o celular e para ler ao sol: tema claro, alto contraste, fonte grande e botão de rega com 72 px de altura.

### Regra do selo

Função pura em `app/services/watering.py` (`compute_badge`), testada em `tests/test_watering_badge.py`.

| Cor | Quando |
|---|---|
| Cinza | Nenhum registro de rega ou chuva |
| Verde | Tempo desde a última água < `BADGE_WARN_RATIO` × intervalo (padrão 75%) |
| Amarelo | Entre 75% e 100% do intervalo |
| Vermelho | Passou do intervalo |

- **"Última água"** é a mais recente entre a última rega e a última chuva registrada (`rain_events`). Chuva anterior ao plantio não conta.
- **O intervalo** vem de `watering_rules`: "recém-plantada" até `phase_until_days` após o plantio, "estabelecida" depois disso. **Os valores atuais são PLACEHOLDER: confirmar com NUGAI/Engenharia.**

### Proteções do registro público de rega

| Proteção | Como |
|---|---|
| Intervalo mínimo por árvore | `MIN_WATERING_INTERVAL_HOURS` (padrão 3 h). Responde 409 com "já foi regada às 08:10" e o selo atual. A linha da árvore é travada (`SELECT … FOR UPDATE`) para que duas regas simultâneas não passem juntas |
| Rate limit por IP | `WATERING_RATE_LIMIT_COUNT` regas a cada `WATERING_RATE_LIMIT_WINDOW_MINUTES`. Responde 429 com `Retry-After`. A contagem fica no Postgres, então funciona com mais de um worker |
| IP | Só o HMAC-SHA256 com `IP_HASH_SALT` é guardado, nunca o IP. Atrás de proxy reverso, configure `FORWARDED_ALLOW_IPS` |
| Honeypot | Campo `website` escondido. Se vier preenchido, a resposta finge sucesso e nada é gravado |
| Validação | Nome opcional com até 60 caracteres; caracteres de controle removidos |
| Headers | CSP restritiva (só scripts do próprio site), `nosniff`, `Referrer-Policy` |

### API pública

| Método | Rota | |
|---|---|---|
| GET | `/api/config` | Centro do mapa, zoom e `BASE_URL` |
| GET | `/api/map/trees` | GeoJSON das árvores plantadas, com a cor do selo |
| GET | `/api/map/zones` | GeoJSON das zonas que já têm polígono |
| GET | `/api/trees/{public_id}` | Dados da página (selo, regas, fotos, espécie, origem) |
| POST | `/api/trees/{public_id}/waterings` | `{"name": "Ana"}`. Responde 201, 409 (intervalo mínimo / árvore não plantada), 429 (rate limit) ou 404 |

---

## Mapa (`/mapa`)

`/` redireciona para cá.

| Visão geral | Card da árvore |
| :---: | :---: |
| ![Mapa](docs/img/map.png) | ![Card](docs/img/map-popup.png) |

- **Camadas:** satélite (Esri World Imagery) e OpenStreetMap. No celular, o seletor vira um botão compacto.
- **Enquadramento:** o mapa começa centralizado em `MAP_CENTER` e, quando há dados, se ajusta à zona e às árvores.
- **Polígonos** das zonas, em amarelo.
- **Um marcador por árvore plantada** (status `planted` ou `attention`), colorido pelo selo de rega. Mudas aguardando plantio e árvores mortas não aparecem. Os selos do mapa saem da mesma função da página da árvore, calculados em lote (número fixo de consultas).
- **Card ao tocar no marcador:** espécie, código, selo e o botão “Ver árvore e registrar rega”.
- **Lista abaixo do mapa,** com resumo (“4 árvores plantadas · 1 precisando de água”) e o botão “Ver no mapa”. Funciona também com leitor de tela ou quando os tiles não carregam.
- **`/mapa#{public_id}`** abre direto o card daquela árvore. É o link “Abrir no mapa do campus” da página da árvore.

---

## Admin (`/admin`)

Login com usuário e senha (JWT, senha em argon2id). O usuário inicial vem de `ADMIN_USERNAME` e `ADMIN_PASSWORD` no seed. Depois de 5 senhas erradas, o IP fica bloqueado por 15 minutos (contagem guardada no banco).

| Tela | O que faz |
|---|---|
| Árvores | Lista com status, lote, zona e selo de rega; cadastro de nova muda (código ARV-NNN automático) |
| Árvore | **Marcar como plantada** com data e local (toque no mapa ou 📍 “Usar minha posição” no celular, que exige HTTPS); editar dados e status; fotos; cuidados (adubação, poda, e excluir regas falsas); QR em PNG/SVG |
| Espécies | Cadastro e revisão. Campo vazio aparece como “informação em revisão”; foto da espécie |
| Zona | Desenhar e editar o polígono no mapa de satélite (tocar para adicionar ponto, arrastar para mover, tocar no ponto para remover) ou **importar GeoJSON** (Polygon/MultiPolygon, Feature ou FeatureCollection com 1 polígono) |
| Chuva e regras | Botão **🌧️ Choveu** (vale para todas as árvores); regras de rega com a marcação “confirmado pela NUGAI/Engenharia”; data da doação |
| QR e etiquetas | PDF A4 com 6 etiquetas por folha (QR + código + nome), só com árvores plantadas; mostra a `BASE_URL` e alerta se ela for local |

| Árvore no admin | Polígono da zona | Etiquetas (PDF A4) |
| :---: | :---: | :---: |
| ![Admin árvore](docs/img/admin-tree.png) | ![Admin zona](docs/img/admin-zone.png) | ![Etiquetas](docs/img/labels-pdf.png) |

Decisões do M3:

- **QR e etiquetas:**
  - Saem para árvores com status `planted` e também `attention`, porque uma árvore em atenção continua plantada e mantém a placa.
  - O PDF e os downloads usam a mesma geração (segno, nível H), e os testes decodificam o QR para conferir a URL.
  - **O nome científico só vai para a etiqueta quando a espécie está “Revisado”**, porque a placa é permanente.
- **Fotos:**
  - O tipo é validado pelo conteúdo, não pela extensão. A imagem é rotacionada conforme o EXIF, reduzida para no máximo 1600 px e regravada como JPEG **sem nenhum metadado** (GPS, aparelho).
  - A data da foto vem do EXIF quando existe.
  - O limite de tamanho é `MAX_UPLOAD_MB`.
- **Horários digitados no admin** (sem fuso) são tratados como horário de São Paulo e gravados em UTC.
- **Exclusão de árvore:** só vale para muda aguardando plantio e sem histórico. Para árvore plantada que se perdeu, use o status “morta”, porque a placa pode já existir.
- **Editor de polígono próprio**, de cerca de 100 linhas sobre o Leaflet, em vez do Leaflet.draw. Assim não depende de `window.L` global nem de ordem de carregamento de scripts.

### API do admin (Bearer JWT)

| Método | Rota |
|---|---|
| POST | `/api/admin/login` |
| GET/POST | `/api/admin/trees` · GET/PATCH/DELETE `/api/admin/trees/{id}` |
| POST | `/api/admin/trees/{id}/plant` (`planted_at`, `lat`, `lng`, `zone_id?`) |
| GET/POST/DELETE | `/api/admin/trees/{id}/photos[/{photo_id}]` |
| GET/POST/DELETE | `/api/admin/trees/{id}/care-events[/{event_id}]` |
| GET | `/api/admin/trees/{id}/qr.png` · `/qr.svg` |
| GET | `/api/admin/labels.pdf[?ids=1&ids=6]` |
| GET/POST/PATCH/DELETE | `/api/admin/species[/{id}]` · POST `/api/admin/species/{id}/photo` |
| GET/POST/PATCH | `/api/admin/origins[/{id}]` |
| GET/PATCH | `/api/admin/zones[/{id}]` · PUT `/api/admin/zones/{id}/geojson` |
| GET/POST/DELETE | `/api/admin/rain-events[/{id}]` |
| GET/PATCH | `/api/admin/watering-rules[/{id}]` |

Documentação interativa em `/docs`.

---

## Colocando no ar

1. **Domínio definitivo e HTTPS** antes de imprimir qualquer placa (veja o aviso sobre a `BASE_URL`). O HTTPS também é exigido pelo “Usar minha posição” do admin.
2. **Proxy reverso** (Caddy ou nginx) na frente da app, com HTTPS.
   - Defina `FORWARDED_ALLOW_IPS` com o IP do proxy para que o rate limit veja o IP real de quem rega.
   - Não exponha a porta 8000 diretamente.
3. **Segredos:** gere `SECRET_KEY` e `IP_HASH_SALT` aleatórios e troque `ADMIN_PASSWORD`.
   - Se o `IP_HASH_SALT` mudar, o rate limit apenas “esquece” os hashes antigos.
4. **Backup** dos dois volumes: `pgdata` (banco) e `uploads` (fotos). Por exemplo, `docker compose exec db pg_dump -U arvores arvores > backup.sql` e uma cópia da pasta de uploads.
5. O rate limit das regas e o bloqueio de login ficam no banco, então funcionam com vários processos ou instâncias.

---

## Publicando na Vercel

A mesma base de código roda no Docker e na Vercel. Na Vercel, o app detecta `VERCEL=1` e passa a:

| No Docker | Na Vercel |
|---|---|
| Pool de conexões com o Postgres local | Sem pool (`NullPool`) e sem cache de prepared statements, compatível com o pooler do **Neon** (PgBouncer em modo transaction) |
| Fotos em disco (`/media/...`) | Fotos no **Vercel Blob** (URL pública absoluta). Ativado pela variável `BLOB_READ_WRITE_TOKEN` |
| IP do cliente via `--proxy-headers` | IP do cliente via `x-real-ip` / `x-forwarded-for`, que a própria Vercel preenche |
| Migrations no start do container | Migrations rodadas por você contra o Neon (passo 2) |

O bloqueio de login fica no banco (tabela `login_attempts`) nos dois casos, para funcionar com várias instâncias.

**Testado aqui:** 240 requisições concorrentes passando por um PgBouncer em modo transaction. A configuração normal (com pool) deu 187 erros 500 de prepared statement; a configuração serverless não deu nenhum.

### Passo a passo

1. **Banco no Neon:** crie um projeto (região **São Paulo, `sa-east-1`**) e copie duas connection strings:
   - **pooled** (host com `-pooler`): é o `DATABASE_URL` do site;
   - **direta** (sem `-pooler`): para as migrations.

   Pode colar como o Neon entrega (`postgresql://…?sslmode=require&channel_binding=require`); o app converte para o formato do asyncpg.
2. **Migrations e seed**, do seu computador, usando a URL **direta**:
   ```bash
   export DATABASE_URL="postgresql://…neon.tech/neondb?sslmode=require"
   alembic upgrade head
   ADMIN_USERNAME=admin ADMIN_PASSWORD="uma-senha-forte" python -m app.seed
   ```
   Repita o `alembic upgrade head` sempre que um PR trouxer uma migration nova.
3. **Projeto na Vercel:** em *Add New → Project*, importe `julianatali31/SIte--rvores`. O FastAPI é detectado sozinho em `app/main.py`, e o `vercel.json` já inclui a pasta `web/` (HTML, CSS, JS) e exclui testes e docs do pacote.
4. **Blob:** em *Storage → Create → Blob* (acesso **público**), conecte ao projeto. Isso cria `BLOB_READ_WRITE_TOKEN`.
5. **Variáveis de ambiente** (*Settings → Environment Variables*, ambiente Production):

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | URL **pooled** do Neon |
   | `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `IP_HASH_SALT` | outro valor gerado do mesmo jeito |
   | `BASE_URL` | o domínio definitivo (passo 6), ex.: `https://arvores.passofundo.ifsul.edu.br` |
   | `MAP_CENTER` | `lat,lng` do campus |
   | `MAX_UPLOAD_MB` | `4` (a Vercel aceita ~4,5 MB por requisição; o admin reduz fotos maiores no navegador) |

   Em produção (`VERCEL_ENV=production`), o app **se recusa a subir** se `SECRET_KEY` ou `IP_HASH_SALT` não estiverem definidos.
6. **Domínio próprio** em *Settings → Domains*. O TI do campus cria um CNAME apontando para a Vercel, e o HTTPS é automático. **Use esse domínio como `BASE_URL`, nunca o `*.vercel.app`.**
7. **Deploy:** cada push na `main` publica em produção, e cada PR ganha uma URL de prévia.

> Prévias de PR usam as variáveis do ambiente *Preview*. Se apontarem para o mesmo banco de produção, regas feitas na prévia entram no banco real. Para testar à vontade, crie um branch do Neon só para as prévias.

---

## Pendências

Itens que dependem de informação externa. O sistema funciona sem eles e mostra “em revisão” ou o aviso de placeholder.

- [ ] **Intervalos de rega** (recém-plantada e estabelecida, e quando uma vira a outra): confirmar com NUGAI/Engenharia e marcar “confirmado” no admin.
- [ ] **Dados das espécies** (descrição, porte, raiz, frutos, curiosidade) e confirmação dos nomes científicos: preencher e marcar “Revisado”.
- [ ] **Data da doação** do Vale Natural Garden Center.
- [ ] **`MAP_CENTER`** com a coordenada real do campus (hoje é um placeholder no centro de Passo Fundo).
- [ ] **Polígono da Zona 1:** desenhar no admin ou importar GeoJSON.
- [ ] **`BASE_URL`** definitiva.
- [ ] **M5 (opcional):** chuva automática via Open-Meteo para `MAP_CENTER`. O modelo já está pronto (`rain_events.source = automatic`); falta o job e o limiar de milímetros, que também é decisão da NUGAI/Engenharia.

---

## Modelo de dados

| Tabela | Para quê |
|---|---|
| `species` | Espécies. Campos botânicos vazios aparecem como "informação em revisão"; `data_review_status` vai de `pending` a `reviewed` |
| `origins` | Doador das mudas (seed: Vale Natural Garden Center, 15 mudas) |
| `planting_zones` | Zonas de plantio, com polígono GeoJSON opcional (seed: Zona 1 — Lago, sem polígono) |
| `trees` | As 15 mudas: `code` (ARV-001…), `public_id` (vai no QR), status, lote, coordenada |
| `care_events` | Regas, adubação, poda. Guarda o hash do IP, nunca o IP |
| `rain_events` | Chuva no campus inteiro; conta como "última água" para o selo |
| `photos` | Fotos por árvore (só o admin envia) |
| `users` | Admin, senha em argon2id |
| `login_attempts` | Tentativas de login erradas (hash do IP), para o bloqueio temporário |
| `watering_rules` | Intervalo de rega por fase. **Valores do seed são PLACEHOLDER: confirmar com NUGAI/Engenharia** |

**Seed:** ARV-001..005 araçá, ARV-006..010 cereja-do-mato, ARV-011..015 guabiju. O lote 1 (ARV-001, 006, 007 e 011) já está ligado à Zona 1. Todas começam em `awaiting_planting`.

---

## Decisões

- **Sem triggers que atualizam a própria tabela.** "Última rega" e "última água" saem de uma query (`MAX(performed_at)`) apoiada no índice `(tree_id, type, performed_at)`. `updated_at` é preenchido pelo ORM.
- **Enums em inglês no banco** (`awaiting_planting`, `planted`, `attention`, `dead`), gravados como `VARCHAR + CHECK` em vez de enum nativo do Postgres, o que deixa as migrations mais simples. Os rótulos em pt-BR ficam em `app/models/enums.py`.
- **UTC no banco, `America/Sao_Paulo` na tela.** Todas as colunas de data e hora são `timestamptz`.
- **Integridade no banco:** árvore `planted` ou `attention` exige `planted_at`; `lat` e `lng` são preenchidas juntas e dentro dos limites válidos.
- **`public_id`:** 8 caracteres de `secrets`, em um alfabeto sem caracteres ambíguos (sem `0 o 1 l i`), únicos no banco.
- **Dados agronômicos não inventados:** nem as espécies nem a data de doação vêm preenchidas, e as regras de rega estão marcadas `is_placeholder`.
- **Sem segredos no repositório:** tudo vem do `.env` (veja o `.env.example`). O admin inicial vem de `ADMIN_USERNAME` e `ADMIN_PASSWORD`.

---

## Estrutura

```
app/
  core/      config, db, segurança, ids, fuso horário
  models/    uma tabela por arquivo
  seed.py
alembic/     migrations
tests/
  schemas/   Pydantic (entrada e saída da API)
  services/  regras puras (selo, textos, GeoJSON), rate limit, fotos, QR, PDF, montagem da página
  routers/   rotas HTTP (público, mapa, admin)
web/
  tree.html, map.html, admin/index.html
  js/        ES modules (type="module"); js/admin/ é o SPA do admin
  css/
  vendor/    Leaflet 1.9.4 servido localmente (sem CDN)
```
