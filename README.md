# CyberEdge Gym

Landing page em português para os serviços de infraestrutura edge e API de
captação de contatos para academias. A API registra solicitações e permite a
uma equipe autorizada consultar e atualizar seu andamento; não controla catracas
ou armazena biometria.

## Arquitetura

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| Site | HTML, JavaScript, Tailwind CSS, GitHub Pages | Formulário acessível, confirmação de envio e efeitos visuais opcionais |
| API | Python 3.12, FastAPI, Pydantic | Validação, autenticação administrativa, limites e respostas HTTP |
| Domínio | `backend/service.py` | Criação idempotente e regras de atualização de status |
| Armazenamento | SQLite WAL, `backend/repository.py` | Transações, índices de filtro e persistência local |

O build gera apenas os arquivos públicos em `dist/`. O CSS é compilado
localmente. Three.js e Tone.js são optativos e carregados com versões fixas e
SRI; se estiverem indisponíveis, o formulário continua funcionando.

## Desenvolvimento

Requer Python 3.12, Node.js 24 (>= 24.8) e Make.

```sh
make setup
cp backend/.env.example backend/.env
make api                 # http://localhost:8000/docs
# Em outro terminal:
make web                 # http://localhost:5500/#contact
```

O backend lê `backend/.env` quando é executado como acima. O ambiente do
processo tem precedência. O segredo administrativo não é necessário para
captar leads localmente: sem ele, as rotas administrativas retornam 503.
Em alternativa ao Python local, use `docker compose up --build api` e
`make web`. O Compose expõe a API apenas no loopback e guarda o banco em volume.

### Variáveis

| Variável | Padrão local | Uso |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `test` ou `production` |
| `DATABASE_URL` | `cyberedge.db` | Caminho de um arquivo SQLite; não é uma URL de rede |
| `ALLOWED_ORIGINS` | `http://localhost:5500,http://127.0.0.1:5500` | Origens exatas, sem barra final. Use HTTPS em produção ou vazio para não permitir acesso cross-origin |
| `ADMIN_TOKEN` | vazio | Segredo com no mínimo 32 caracteres ASCII imprimíveis sem espaços; obrigatório em produção |
| `CONTACT_RATE_LIMIT` | `10` | Solicitações de contato por endereço dentro da janela |
| `CONTACT_RATE_WINDOW_SECONDS` | `60` | Duração da janela |
| `CONTACT_RATE_MAX_CLIENTS` | `10000` | Limite de endereços simultâneos em memória |
| `MAX_REQUEST_BYTES` | `4096` | Tamanho máximo do JSON nas rotas de escrita |
| `CYBEREDGE_API_URL` | `http://localhost:8000` | Configuração pública do build do site, não um segredo. Produção exige uma origem HTTPS |

Gere o token com `python -c 'import secrets; print(secrets.token_urlsafe(32))'`
e guarde-o no gerenciador de segredos do backend. Nunca o inclua no site,
em logs ou no repositório. No Compose local, exporte `ADMIN_TOKEN` antes de
subir o contêiner, caso precise usar as rotas administrativas.

## API

| Método e rota | Contrato |
|---|---|
| `GET /` | Liveness: o processo está respondendo |
| `GET /readyz` | Readiness: a tabela de leads está acessível |
| `POST /api/contato` | JSON `nome`, `academia`, `whatsapp`, `tier` (`start`, `pro`, `enterprise`). Retorna 201 com o lead criado |
| `GET /api/leads` | Bearer obrigatório; filtro `status` e/ou `tier`, `limit` 1–100, `offset` 0–100000, `sort` `newest` (padrão) ou `oldest` por ID |
| `PATCH /api/leads/{id}` | Bearer obrigatório; recebe `status` e `esperado`. Retorna 409 se outro operador já mudou o status |

Os status são `novo`, `contatado`, `fechado` e `perdido`. Envie uma
`Idempotency-Key` opaca de 16 a 64 caracteres alfanuméricos, `_` ou `-`
para poder repetir um envio cujo resultado não foi confirmado. Com a mesma
chave e conteúdo normalizado, a API devolve novamente a resposta de criação;
com a mesma chave e outro conteúdo, devolve 409. Use uma chave nova para
cada solicitação distinta.

```sh
curl -fsS http://localhost:8000/api/contato \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"nome":"Pessoa Teste","academia":"Academia Exemplo","whatsapp":"11999998888","tier":"pro"}'

curl -fsS 'http://localhost:8000/api/leads?status=novo&limit=10' \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl -fsS -X PATCH http://localhost:8000/api/leads/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"contatado","esperado":"novo"}'
```

Erros da API usam `{"error":{"code":"invalid_request","message":"…","fields":[…]}}`
(campos opcionais) sem ecoar a solicitação. O limite de solicitações retorna
429 e `Retry-After`. A documentação interativa está disponível apenas fora
de produção. O CORS do site permite somente a submissão pública, não operações
administrativas cross-origin.

## Verificação

- `make check`: lint HTML/JS/Python, formatação Python, mypy estrito, testes
  de API com cobertura de linha/branch mínima de 90%, testes Chromium e auditorias.
- `make lock-python`: atualiza os locks de Python após mudanças nos arquivos
  `.in`. Use Python 3.12 em Linux para reproduzir os locks de CI.
- `docker build -t cyberedgegym-api backend`: constrói a imagem de runtime
  multi-stage não-root.

## Publicação e operação

1. Suba a imagem da API atrás de um proxy HTTPS. Configure `ADMIN_TOKEN` e
   `ALLOWED_ORIGINS=https://joaovictoreth1.github.io`. Monte armazenamento
   persistente gravável pelo UID/GID 10001 em `/data`. A imagem usa
   `ENVIRONMENT=production` e `DATABASE_URL=/data/cyberedge.db` por padrão.
2. Antes de atualizar um banco existente, faça backup com a API de backup
   do SQLite para incluir transações do WAL; valide a restauração e restrinja
   o acesso ao arquivo e aos backups. O startup mantém os leads existentes e
   cria índices e a tabela de idempotência de forma aditiva.
3. No GitHub, selecione GitHub Actions como origem do Pages e configure a
   variável `CYBEREDGE_API_URL` com a origem HTTPS da API. O pipeline publica
   `dist/` somente após os checks do backend e do frontend passarem no
   branch `main`. O pipeline do Pages não implanta a API.
4. Monitore `/readyz`, 429/503, uso de disco e espaço para backups. Defina
   retenção e descarte de leads e backups conforme a política aplicável.

O SQLite e o limitador local destinam-se a uma instância com disco persistente
e um worker. Configure o proxy para limitar taxa, conexões e tempo de leitura
de solicitações; informe somente IPs confiáveis em `FORWARDED_ALLOW_IPS` para
que os limites vejam o cliente real. Para escalar a API horizontalmente,
use armazenamento compartilhado transacional e limite distribuído antes de
adicionar réplicas — não compartilhe o arquivo SQLite entre hosts.
