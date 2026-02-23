# Portal CISP — Consulta de Crédito

Aplicação web para consulta de avaliação analítica de crédito via API CISP, com persistência em PostgreSQL e integração com Power BI.

---

## Como Rodar (desenvolvimento local)

**1. Pré-requisitos**
```
Python 3.11+
PostgreSQL acessível
```

**2. Instale as dependências**
```bash
pip install -r requirements.txt
```

**3. Configure as variáveis de ambiente**

Crie um arquivo `.env` na raiz (nunca commitar):
```env
CISP_USERNAME=seu_usuario
CISP_PASSWORD=sua_senha
POSTGRES=senha_do_banco
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=dbDataLakePrd
DB_USER=postgres
DB_SCHEMA=scsilverlayer
```

**4. Execute**
```bash
python app.py
```
Acesse: http://localhost:5000

---

## Deploy em Produção (Linux + Docker)

### Primeira vez no servidor

```bash
# Copie o script para o servidor
scp setup-servidor.sh usuario@ip-servidor:/tmp/

# Execute no servidor
ssh usuario@ip-servidor
sudo bash /tmp/setup-servidor.sh
```

O script instala Docker, clona o repositório, cria o `.env` e sobe a aplicação automaticamente.

### Deploy automático (GitHub Actions)

A cada `git push origin main`, o GitHub Actions conecta no servidor via SSH e faz:
```
git pull → docker-compose build → docker-compose up -d → prune
```

**Secrets necessários no GitHub**
> Acesse: https://github.com/roccorenan/CISP/settings/secrets/actions

| Secret | Valor |
|---|---|
| `SERVER_HOST` | IP do servidor Linux |
| `SERVER_USER` | Usuário SSH (ex: `root`) |
| `SERVER_SSH_KEY` | Chave privada gerada pelo `setup-servidor.sh` |
| `SERVER_PORT` | `22` |

---

## Endpoints da API

| Método | URL | Descrição |
|---|---|---|
| GET | `/` | Portal Web |
| GET | `/api/health` | Status da aplicação |
| GET | `/api/sincronizar/<raiz>` | Busca na CISP e grava no banco |
| GET | `/api/cliente/<raiz>` | Retorna dados do banco |

**Uso no Power BI:**
```
Web.Contents("http://IP-DO-SERVIDOR:5000/api/sincronizar/45543915")
```

---

## Operações úteis no servidor

```bash
# Ver logs em tempo real
docker logs cisp-web -f --tail=100

# Reiniciar a aplicação
cd /opt/cisp && docker-compose restart

# Ver status do container
docker-compose ps

# Atualizar variáveis de ambiente
nano /opt/cisp/.env
docker-compose up -d
```
