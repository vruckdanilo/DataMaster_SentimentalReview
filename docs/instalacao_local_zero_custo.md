# 🏠 Instalação Local Zero Custo

![Local Installation](https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExbDV6dGNicnhvMmI2dzVhMDQ5Nnd5ZGR5OHA0YjJubmp4cDR5bHJlbiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/lYZjoIy0UOEJa/giphy.gif) - DataMaster SentimentalReview


Este guia te leva do zero ao ambiente completo funcionando em menos de 10 minutos. Eu otimizei tudo para rodar no seu Docker Desktop sem precisar de cloud, créditos ou cartão de crédito.

---

## 📋 Índice

- [🎯 Pré-requisitos](#-pré-requisitos)
- [⚙️ Configuração do Ambiente](#️-configuração-do-ambiente)
- [🚀 Instalação Automática](#-instalação-automática)
- [✅ Validação e Smoke Tests](#-validação-e-smoke-tests)
- [🔧 Troubleshooting](#-troubleshooting)
- [📖 Diário de Bordo](#-Diário-de-Bordo)

---

## 📋 Pré-requisitos


### Sistema Operacional
- **Linux:** Ubuntu 20.04+, CentOS 8+, ou similar
- **macOS:** 10.15+ (Catalina ou superior)
- **Windows:** Windows 10/11 com WSL2

### Hardware Mínimo
| Componente | Mínimo | Recomendado | Observações |
|------------|--------|-------------|-------------|
| **RAM** | 8GB | 16GB | Spark é memory-intensive |
| **CPU** | 4 cores | 8 cores | Processamento paralelo |
| **Disco** | 20GB livre | 50GB livre | Imagens Docker + dados |


### Software Obrigatório

**1. Docker Desktop**
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# macOS
brew install --cask docker

# Windows
# Baixar do site oficial: https://docker.com/products/docker-desktop
```

**2. Docker Compose V2**
```bash
# Verificar se já está instalado
docker compose version

# Se não estiver, instalar
sudo apt-get install docker-compose-plugin  # Ubuntu
brew install docker-compose                 # macOS
```

**3. Git**
```bash
sudo apt-get install git  # Ubuntu
brew install git          # macOS
```

### 🔍 Verificação da Instalação

Pré-requisitos
```bash
# Verificar Docker
docker --version
docker compose version

# Verificar recursos
free -h                    # RAM disponível
df -h                      # Espaço em disco
nproc                      # Número de CPUs

# Testar Docker
docker run hello-world
```

---

## ⚙️ Configuração do Ambiente



### 1. Clone do Repositório
```bash
git clone <repository-url>
cd DataMaster_SentimentalReview
```

### 2. Configuração do .env

O projeto já vem com um [`.env`](../.env) pré-configurado, mas você pode personalizar:

```bash
# O arquivo .env já está configurado e pronto para uso
# Você pode editá-lo se necessário:
nano [`.env`](../.env)
```

**Variáveis principais do [`.env`](../.env):**

```bash
# ====================================================================
# 🔑 APIS EXTERNAS (OPCIONAIS PARA DEMO)
# ====================================================================


# ====================================================================
# 🗄️ CONFIGURAÇÕES DE BANCO
# ====================================================================

POSTGRES_DB=airflow_db
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow

# ====================================================================
# 💾 MINIO (S3 LOCAL)
# ====================================================================

MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123
MINIO_ENDPOINT=minio:9000

# ====================================================================
# ⚡ SPARK (OTIMIZADO PARA LOCAL)
# ====================================================================

SPARK_DRIVER_MEMORY=512m
SPARK_EXECUTOR_MEMORY=512m
SPARK_DRIVER_CORES=1
SPARK_EXECUTOR_CORES=1

# ====================================================================
# 🔄 AIRFLOW
# ====================================================================

AIRFLOW_ADMIN_USERNAME=admin
AIRFLOW_ADMIN_PASSWORD=admin
```

### 3. Configuração de Recursos Docker

**Docker Desktop Settings:**
- **Memory:** 6-8GB (mínimo 4GB)
- **CPUs:** 4-6 cores
- **Disk:** 50GB+ espaço livre

**Linux - Configurar limites:**
```bash
# Editar daemon.json
sudo nano /etc/docker/daemon.json

{
  "default-runtime": "runc",
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}

# Reiniciar Docker
sudo systemctl restart docker
```

---

## 🚀 Inicialização do Sistema


![Automated Installation](https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZWNzamFqMGYyOW84ZmYxZjZnbXVra2dxcThpbHAwMWhkeHBmbDY3bCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l1RCv0zXG5PhNRFEWl/giphy.gif)

### Método 1: Script Automático (Recomendado)

```bash
# Executar script principal
[`./scripts/start.sh`](../scripts/start.sh)

# O script faz TUDO automaticamente:
# ✅ Verifica pré-requisitos
# ✅ Limpa ambiente anterior
# ✅ Constrói imagens Docker (5-10 min)
# ✅ Inicia serviços principais
# ✅ Configura buckets MinIO
# ✅ Cria tópicos Kafka
# ✅ Configura conexões Airflow
# ✅ Executa health checks
# ✅ Mostra URLs de acesso
```

**Opções do script:**
```bash
# Instalação limpa (remove dados anteriores)
[`./scripts/start.sh`](../scripts/start.sh) --clean-volumes

# Pular testes automáticos
[`./scripts/start.sh`](../scripts/start.sh) --no-tests

# Não reconstruir imagens
[`./scripts/start.sh`](../scripts/start.sh) --no-build

# Recriar apenas Superset
[`./scripts/start.sh`](../scripts/start.sh) --recreate-superset

# Ver todas as opções
[`./scripts/start.sh`](../scripts/start.sh) --help
```

### Método 2: Manual (Para Debugging)

```bash
# 1. Construir imagens base
docker compose --profile build build spark-base

# 2. Construir demais serviços
docker compose build

# 3. Iniciar serviços
docker compose up -d

# 4. Aguardar inicialização (5-10 min)
docker compose ps

# 5. Configurar MinIO
docker compose exec minio mc alias set local http://localhost:9000 minio minio123
docker compose exec minio mc mb local/datalake

# 6. Criar usuário admin
docker compose exec airflow-webserver airflow users create \
  --username admin --password admin --firstname Admin \
  --lastname User --role Admin --email admin@example.com
```

### Acompanhamento da Instalação

**Logs em tempo real:**
```bash
# Todos os serviços
docker compose logs -f

# Serviço específico
docker compose logs -f airflow-webserver
docker compose logs -f spark-master
docker compose logs -f superset
```

**Status dos containers:**
```bash
# Verificar status
docker compose ps

# Verificar saúde
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

---

## ✅ Validação e Smoke Tests



### Teste Automático (via script)
```bash
# Executar testes integrados
[`./scripts/start.sh`](../scripts/start.sh) --no-build  # Pula rebuild, só testa
```

### Testes Manuais

**1. Testar Endpoints Principais**
```bash
# Airflow
curl -f http://localhost:8089/health
echo "Airflow: $?"

# Superset  
curl -f http://localhost:8088/health
echo "Superset: $?"

# MinIO
curl -f http://localhost:9000/minio/health/live
echo "MinIO: $?"

# Trino
curl -f http://localhost:8080/v1/info
echo "Trino: $?"

# Spark Master
curl -f http://localhost:8082
echo "Spark: $?"

# Mock API
curl -f http://localhost:3001/textsearch
echo "Mock API: $?"
```

**2. Testar Conectividade Interna**
```bash
# Kafka
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# PostgreSQL
docker compose exec postgres-airflow pg_isready -U airflow

# MySQL
docker compose exec mysql mysqladmin ping -h localhost
```

**3. Testar Integração Spark + MinIO**
```bash
# Executar job de teste
docker compose exec spark-master spark-submit \
  --class org.apache.spark.examples.SparkPi \
  --master spark://spark-master:7077 \
  /opt/bitnami/spark/examples/jars/spark-examples_2.12-3.5.0.jar 10
```

### Checklist de Validação

| Serviço | URL | Status Esperado | Credenciais |
|---------|-----|-----------------|-------------|
| ✅ Airflow | http://localhost:8089 | Login page | admin/admin |
| ✅ Superset | http://localhost:8088 | Login page | admin/admin123 |
| ✅ Trino | http://localhost:8080 | Query interface | - |
| ✅ Spark Master | http://localhost:8082 | Cluster info | - |
| ✅ Spark Worker | http://localhost:8081 | Worker info | - |
| ✅ MinIO Console | http://localhost:9001 | Login page | minio/minio123 |
| ✅ Mock API | http://localhost:3001 | JSON response | - |

---

## 🔧 Troubleshooting

![Troubleshooting](https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTVtbGowdjRvM2VsbHB1eXR4OXc0NzQwNTU5YnJleHE4azl0enZuayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/PnpkimJ5mrZRe/giphy.gif)

### Problemas Comuns

**1. Erro: "Port already in use"**
```bash
# Verificar processos usando as portas
sudo lsof -i :8089  # Airflow
sudo lsof -i :8088  # Superset
sudo lsof -i :8080  # Trino

# Parar processos conflitantes
sudo systemctl stop apache2    # Se houver Apache
sudo systemctl stop nginx      # Se houver Nginx

# Ou mudar portas no [`docker-compose.yml`](../docker-compose.yml)
```

**2. Erro: "Cannot connect to Docker daemon"**
```bash
# Verificar se Docker está rodando
sudo systemctl status docker

# Iniciar Docker
sudo systemctl start docker

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
newgrp docker  # Ou fazer logout/login
```

**3. Erro: "Out of memory" ou containers crashando**
```bash
# Verificar uso de memória
docker stats

# Aumentar memória no Docker Desktop
# Settings > Resources > Memory > 8GB+

# Ou reduzir configurações no [`.env`](../.env)
SPARK_DRIVER_MEMORY=256m
SPARK_EXECUTOR_MEMORY=256m
```

**4. Erro: "No space left on device"**
```bash
# Limpar imagens não utilizadas
docker system prune -f

# Limpar volumes órfãos
docker volume prune -f

# Verificar espaço
df -h
docker system df
```

**5. Containers ficam "unhealthy"**
```bash
# Verificar logs específicos
docker compose logs [service-name]

# Reiniciar serviço específico
docker compose restart [service-name]

# Recriar container
docker compose up -d --force-recreate [service-name]
```

### Debugging Avançado

**Logs detalhados:**
```bash
# Airflow scheduler
docker compose logs -f airflow-scheduler | grep ERROR

# Spark jobs
docker compose logs -f spark-master | grep -i error

# Superset inicialização
docker compose logs -f superset | tail -100
```

**Acesso aos containers:**
```bash
# Entrar no container Airflow
docker compose exec airflow-webserver bash

# Entrar no container Spark
docker compose exec spark-master bash

# Verificar configurações
docker compose exec airflow-webserver env | grep AIRFLOW
```

**Testes de conectividade:**
```bash
# Testar conectividade entre containers
docker compose exec airflow-webserver ping minio
docker compose exec trino ping postgres-airflow
docker compose exec superset ping trino-coordinator
```

### Soluções para Problemas Específicos

**Airflow não carrega DAGs:**
```bash
# Verificar diretório de DAGs
docker compose exec airflow-webserver ls -la /opt/airflow/dags/

# Verificar logs do scheduler
docker compose logs airflow-scheduler | grep -i dag

# Forçar refresh
docker compose exec airflow-webserver airflow dags list-import-errors
```

**Spark jobs falham:**
```bash
# Verificar worker conectado
docker compose exec spark-master curl http://localhost:8082/json/

# Testar job simples
docker compose exec spark-master spark-submit --version

# Verificar configurações MinIO/S3
docker compose exec spark-master env | grep MINIO
```

**Superset não conecta ao Trino:**
```bash
# Testar conectividade
docker compose exec superset ping trino

# Verificar drivers instalados
docker compose exec superset pip list | grep trino

# Testar conexão manual
docker compose exec superset python -c "
import trino
conn = trino.dbapi.connect(host='trino', port=8080, user='admin')
print('Conexão OK')
"
```

---

## 🎯 Primeiros Passos

![Getting Started](https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExY3Y1N3hsZTdqM3l5cG41MTB2dm15ZnNzODg1ZmsyeThoNHlzd3Z6MiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/HNtm9TDgxGza8/giphy.gif)

### Após Instalação Bem-sucedida

**1. Explorar Interfaces**
- Faça login no Airflow (admin/admin)
- Explore a interface do Superset
- Navegue pelo Spark Master UI
- Acesse o MinIO Console

**2. Executar Pipeline de Exemplo**
```bash
# Via Airflow UI
# 1. Acesse http://localhost:8089
# 2. Ative a DAG "datamaster_pipeline_dag_fixed"
# 3. Execute manualmente
# 4. Acompanhe execução

# Via linha de comando
docker compose exec airflow-webserver airflow dags trigger datamaster_pipeline_dag_fixed
```

**3. Explorar Dados**
```bash
# Verificar buckets MinIO
docker compose exec minio mc ls local/datalake/

# Consultar via Trino
docker compose exec trino-coordinator trino --server localhost:8080 --catalog iceberg --schema default
```

**4. Configurar Dashboards**
- Configure conexão Superset → Trino
- Crie datasets baseados nas tabelas Gold
- Desenvolva dashboards de sentimento

### Personalização

**APIs Reais:**
1. Obtenha chave Google Maps API
2. Configure OpenAI API key
3. Descomente variáveis no [`.env`](../.env)
4. Reinicie containers

**Configurações de Produção:**
1. Aumente recursos Spark
2. Configure SSL/TLS
3. Implemente backup automático
4. Configure alertas por email

### Monitoramento Contínuo

```bash
# Script de monitoramento
cat > monitor.sh << 'EOF'
#!/bin/bash
while true; do
  echo "=== $(date) ==="
  docker compose ps --format "table {{.Name}}\t{{.Status}}"
  echo ""
  sleep 60
done
EOF

chmod +x monitor.sh
./monitor.sh
```

---

## 📖 Diário de Bordo

### Atalhos e Truques que uso no dia a dia

**1. Aliases úteis:**
```bash
# Adicionar ao ~/.bashrc
alias dps='docker compose ps'
alias dlogs='docker compose logs -f'
alias dexec='docker compose exec'
alias ddown='docker compose down'
alias dup='docker compose up -d'
```

**2. Scripts de desenvolvimento:**
```bash
# Restart rápido do Airflow
restart_airflow() {
  docker compose restart airflow-webserver airflow-scheduler
}

# Limpar logs antigos
clean_logs() {
  docker compose exec airflow-webserver find /opt/airflow/logs -name "*.log" -mtime +7 -delete
}
```

**3. Configurações otimizadas:**
- Uso health checks para evitar race conditions
- Configurei timeouts generosos para primeira inicialização
- Implementei retry automático com backoff exponencial
- Separei configurações por ambiente ([`.env`](../.env))

**4. Debugging eficiente:**
- Sempre verifico logs antes de reiniciar containers
- Uso `docker stats` para monitorar recursos
- Mantenho scripts de teste para validação rápida
- Documento todos os problemas e soluções

### Resultados

- ✅ **Automação completa:** Um script resolve tudo
- ✅ **Configuração robusta:** Health checks e validações
- ✅ **Troubleshooting detalhado:** Soluções para problemas reais
- ✅ **Otimização de recursos:** Funciona em hardware limitado
- ✅ **Documentação prática:** Baseada em experiência real

---

## 📊 Mídia Sugerida para este Doc

| Arquivo | Descrição | Momento de Uso |
|---------|-----------|----------------|
| `docs/media/docker-startup.gif` | Containers subindo em sequência | Início do documento |
| `docs/media/health-checks.gif` | Validação automática de serviços | Seção de validação |
| `docs/media/troubleshooting-flow.gif` | Fluxo de debugging | Seção troubleshooting |
| `docs/media/first-login.gif` | Primeiro acesso às interfaces | Próximos passos |

---

**Dica Rápida:** Se algo der errado, sempre comece com `docker compose logs [service]`. 90% dos problemas ficam claros nos logs.

**Erro que já cometi aqui:** Tentar acessar serviços antes dos health checks passarem. Paciência é fundamental na primeira inicialização!

---
