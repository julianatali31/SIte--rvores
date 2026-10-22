# Plantando Ideias — Árvores do Campus

Site do projeto de extensão do **IFSul Campus Passo Fundo**. Cada árvore plantada recebe uma placa com QR Code que leva a uma página pública, onde qualquer pessoa vê **quando a árvore foi regada pela última vez** e pode registrar uma rega na hora.

> **Status:** M1 (esqueleto, modelo, seed) e M2 (página pública, selo e registro de rega) concluídos.
> Próximos: M3 admin, chuva manual, QR e etiquetas; M4 mapa.

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
| GET | `/api/trees/{public_id}` | Dados da página (selo, regas, fotos, espécie, origem) |
| POST | `/api/trees/{public_id}/waterings` | `{"name": "Ana"}`. Responde 201, 409 (intervalo mínimo / árvore não plantada), 429 (rate limit) ou 404 |

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
  services/  regras puras (selo, textos), rate limit, montagem da página
  routers/   rotas HTTP
web/         HTML/CSS/JS vanilla (ES modules), Leaflet 1.9.4 servido localmente em web/vendor
```
