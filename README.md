# DataMaster SentimentalReview 🏦📊

<div align="center">

![Data Engineering Magic](https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ2lwb2czcHg1d2hsdmNyOGwwNGtmZzAzaDBreGJlbjE3ZXRocjNhcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/6A8RJnAVc8Bz0DCX5w/giphy.gif)

*Plataforma moderna de análise de sentimento para agências Santander*

</div>

**Uma plataforma completa de análise de sentimento para agências Santander em São Paulo, implementando um Data Lakehouse moderno 100% local e sem custos de cloud.**

Eu criei este projeto para demonstrar expertise em engenharia de dados moderna, combinando as melhores práticas de Data Lakehouse, processamento distribuído e análise de sentimento em tempo real. É um ambiente que emula perfeitamente serviços de cloud (AWS, GCP, Azure) mas roda inteiramente no seu Docker Desktop.

---

## 📋 Índice

- [🚀 Demonstração Rápida](#-demonstração-rápida)
- [🏗️ Arquitetura](#️-arquitetura)
- [📁 Mapa do Repositório](#-mapa-do-repositório)
- [⚡ Como Rodar Localmente](#-como-rodar-localmente)
- [🎯 Por que isto demonstra expertise?](#-Resultados-Observáveis)
- [📚 Documentação Detalhada](#-documentação-detalhada)
- [🔧 Troubleshooting](#-troubleshooting)
- [🛣️ Roadmap](#️-roadmap)

---

## 🚀 Demonstração Rápida


### Instalação em 1 comando:
```bash
./scripts/start.sh
```

![Terminal Magic](https://media.giphy.com/media/ZVik7pBtu9dNS/giphy.gif)

### Instalação em 5 passos:
```bash
# 1. Clone e entre no diretório
git clone <repo> && cd DataMaster_SentimentalReview

# 2. Configure as variáveis (opcional - já tem defaults)
cp .env.example .env

# 3. Execute o script de inicialização
./scripts/start.sh

# 4. Aguarde ~5 minutos (primeira execução)
# 5. Acesse as interfaces (URLs abaixo)
```

### 🌐 Interfaces Disponíveis:
| Serviço | URL | Credenciais | Propósito |
|---------|-----|-------------|-----------|
| **Airflow** | http://localhost:8089 | admin/admin123 | Orquestração de pipelines |
| **Superset** | http://localhost:8088 | admin/admin123 | Dashboards e visualização |
| **Trino** | http://localhost:8080 | - | Query engine SQL |
| **Spark Master** | http://localhost:8082 | - | Cluster Spark UI |
| **MinIO Console** | http://localhost:9001 | minioadmin/minioadmin123 | Object Storage S3-like |
| **Mock API** | http://localhost:3001 | - | Simulador Google Maps |

---

## 🏗️ Arquitetura

<div align="center">

![Data Architecture](https://media.giphy.com/media/xT9IgzoKnwFNmISR8I/giphy.gif)

*Arquitetura Data Lakehouse Moderna*

</div>



### Diagrama ASCII (Fallback)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Google Maps   │───▶│  Apache Kafka   │───▶│ Apache Airflow  │
│   Mock API      │    │   Streaming     │    │ Orquestração    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA LAKEHOUSE (MinIO S3)                       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │
│  │ Landing │─▶│ Bronze  │─▶│ Silver  │─▶│  Gold   │              │
│  │  (Raw)  │  │(Struct) │  │(+NLP)   │  │(Agg)    │              │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │  Apache Trino   │───▶│ Apache Superset │
                    │ Query Engine    │    │   Dashboards    │
                    └─────────────────┘    └─────────────────┘
```

---

## 📁 Mapa do Repositório

| Pasta/Arquivo | Propósito | Tecnologia Principal |
|---------------|-----------|---------------------|
| `scripts/start.sh` | 🚀 Script principal de inicialização | Bash + Docker |
| `docker-compose.yml` | 🐳 Orquestração completa (13 serviços) | Docker Compose |
| `mnt/airflow/dags/` | 🔄 DAGs de orquestração | Apache Airflow |
| `mnt/spark/jobs/` | ⚡ Jobs PySpark (Landing→Bronze→Silver→Gold) | PySpark + Delta Lake |
| `mnt/airflow/scripts/` | 🛠️ Módulos auxiliares (APIs, controle, qualidade) | Python |
| `docker/` | 🏗️ Dockerfiles customizados | Docker + Bitnami |
| `requirements.txt` | 📦 138 dependências categorizadas | Python |
| `.env` | ⚙️ Configurações essenciais | Environment Variables |
| `docs/` | 📚 Documentação técnica completa | Markdown |

---

## ⚡ Como Rodar Localmente

![Docker Containers](https://media.giphy.com/media/4FQMuOKR6zQRO/giphy.gif)

### Pré-requisitos
- **Docker Desktop** (4GB+ RAM recomendado)
- **8GB RAM** total no sistema
- **10GB** espaço livre em disco
- **Sistema:** Linux, macOS ou Windows com WSL2

### Instalação Automática

![Automation](https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZW04Y3lodHJzdmVoeWdoZjd0c3VreGJvdmlmeGNteG00Yzhnb3JhZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/1lxryzbQaqo49cKhCw/giphy.gif)

```bash
# Clone o repositório
git clone <repo-url>
cd DataMaster_SentimentalReview

# Execute o script mágico ✨
./scripts/start.sh

# Aguarde ~5 minutos na primeira execução
# O script faz TUDO automaticamente:
# ✅ Verifica pré-requisitos
# ✅ Constrói imagens Docker
# ✅ Inicia 13 serviços
# ✅ Configura buckets MinIO
# ✅ Cria tópicos Kafka
# ✅ Configura conexões Airflow
# ✅ Executa health checks
```

### Validação Rápida
```bash
# Verificar status dos containers
docker compose ps

# Testar endpoints principais
curl http://localhost:8089/health  # Airflow
curl http://localhost:8088/health  # Superset
curl http://localhost:9000/minio/health/live  # MinIO
```

---

## 🧪 Resultados Observáveis

<div align="center">

![Expert Level](https://media.giphy.com/media/3oriO0OEd9QIDdllqo/giphy.gif)



</div>

**Arquitetura de Dados Moderna:**
- [x] **Data Lakehouse** com arquitetura medalhão (Landing→Bronze→Silver→Gold)
- [x] **Delta Lake** para ACID transactions e time travel
- [x] **Apache Iceberg** como alternativa (implementado em memórias)
- [x] **MinIO S3-compatible** simulando cloud storage
- [x] **Particionamento inteligente** por data/bairro/run_id

**Processamento Distribuído:**
- [x] **Apache Spark** com otimizações AQE (Adaptive Query Execution)
- [x] **PySpark UDFs** para análise de sentimento customizada
- [x] **Configurações otimizadas** para ambiente local (5-6GB RAM vs 12GB)
- [x] **Jobs idempotentes** com controle de reprocessamento

**Orquestração e Streaming:**
- [x] **Apache Airflow** com DAGs complexas e dependências
- [x] **Apache Kafka** para streaming em tempo real
- [x] **Controle incremental** por bairros com persistência
- [x] **Rate limiting** e backoff exponencial para APIs

**Qualidade e Governança:**
- [x] **Data Quality checks** automatizados
- [x] **Logging estruturado** com diferentes níveis
- [x] **Retry policies** e tratamento de falhas
- [x] **Versionamento de dados** com Delta Lake

**DevOps e Infraestrutura:**
- [x] **Docker Compose** com 13 serviços orquestrados
- [x] **Health checks** e monitoring automático
- [x] **Scripts de inicialização** robustos com validações
- [x] **Configuração via .env** para diferentes ambientes

**Análise Avançada:**
- [x] **NLP em português brasileiro** (Hugging Face + Presidio)
- [x] **Detecção de PII** com anonimização automática
- [x] **Análise de risco reputacional** baseada em keywords
- [x] **Dashboards interativos** com Apache Superset

### 🏆 Diferenciais Técnicos

![Achievement Unlocked](https://media.giphy.com/media/3o6fJ1BM7R2EBRDnxK/giphy.gif)

1. **Zero Custo:** Emula AWS/GCP/Azure inteiramente local
2. **Produção-Ready:** Configurações enterprise com fallbacks
3. **Educacional:** Código documentado e explicado em português
4. **Escalável:** Arquitetura preparada para cloud migration
5. **Completo:** Pipeline end-to-end funcional com dados reais

---

## 📚 Documentação Detalhada

| Documento | Foco | Audiência |
|-----------|------|-----------|
| [🏗️ Arquitetura](docs/arquitetura.md) | Design técnico, trade-offs, diagramas | Arquitetos, Engenheiros |
| [💻 Instalação Local](docs/instalacao_local_zero_custo.md) | Setup passo-a-passo, troubleshooting | Desenvolvedores, DevOps |
| [🔄 Pipeline & DAGs](docs/pipeline_e_dags.md) | Fluxo de dados, orquestração | Engenheiros de Dados |
| [🧠 Análise de Sentimentos](docs/analise_sentimentos.md) | NLP, modelos, custos | Data Scientists |
| [❓ FAQ & Troubleshooting](docs/faq_troubleshooting.md) | Perguntas frequentes e soluções | Todos |

---

## 🔧 Troubleshooting



### 🚨 Problemas Comuns

**Container não sobe:**
```bash
# Verificar recursos
docker system df
docker system prune -f  # Liberar espaço

# Verificar logs
docker compose logs [service-name]
```

**Porta ocupada:**
```bash
# Verificar processos
sudo lsof -i :8089  # Airflow
sudo lsof -i :8088  # Superset

# Parar serviços conflitantes
sudo systemctl stop apache2  # Se usar Apache
```

**Memória insuficiente:**
```bash
# Verificar uso atual
free -h
docker stats

# Otimizar configurações no .env
SPARK_DRIVER_MEMORY=256m
SPARK_EXECUTOR_MEMORY=256m
```

### 💡 Dicas Rápidas

- **Primeira execução:** Aguarde 5-10 minutos para download das imagens
- **Reinicialização:** Use `./scripts/start.sh --no-build` para pular rebuild
- **Limpeza completa:** `./scripts/start.sh --clean-volumes` (⚠️ perde dados)
- **Logs detalhados:** `docker compose logs -f [service]`

### 🎯 Erros que já cometi aqui

![Lessons Learned](https://media.giphy.com/media/d3mlE7uhX8KFgEmY/giphy.gif)

1. **Não aguardar health checks:** Tentava acessar serviços antes de estarem prontos
2. **Misturar credenciais:** MinIO Console usa `minioadmin/minioadmin123`, mas API interna usa `minio/minio123`
3. **Esquecer volumes:** Dados perdidos ao recriar containers sem volumes
4. **Portas conflitantes:** Airflow na 8089, não 8080 (conflito com Trino)

---

## 🛣️ Roadmap

<div align="center">

![Future Vision](https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExNG5zZDVnM3lqZzEzd2F3eTRxcDZyMTQzeDM0Yjk4b3U0YmJ1bG5uYSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/rBA9YKPPA4v7DXPdvg/giphy.gif)

*Visão de Futuro do Projeto*

</div>

### 🎯 Próximas Melhorias

**Curto Prazo (1-2 semanas):**
- [ ] **API Real Google Maps:** Substituir mock por integração real
- [ ] **Alertas Proativos:** Slack/Email para falhas de pipeline
- [ ] **Métricas Prometheus:** Observabilidade avançada
- [ ] **Testes Automatizados:** PyTest para jobs Spark

**Médio Prazo (1-2 meses):**
- [ ] **MLflow Integration:** Versionamento de modelos NLP
- [ ] **Great Expectations:** Data quality framework
- [ ] **Apache Ranger:** Governança e segurança
- [ ] **Kubernetes Deployment:** Migração para K8s

**Longo Prazo (3-6 meses):**
- [ ] **Real-time Streaming:** Kafka Streams + ksqlDB
- [ ] **Machine Learning:** Modelos preditivos de satisfação
- [ ] **Multi-tenant:** Suporte a múltiplos bancos
- [ ] **Cloud Migration:** Deploy em AWS/GCP/Azure

### 🔄 Melhorias Contínuas



- **Performance:** Otimização de queries Spark
- **Usabilidade:** Interface web para configuração
- **Documentação:** Vídeos tutoriais e workshops
- **Comunidade:** Contribuições open source

---

## 📖 Diário de Bordo

![Behind the Scenes](https://media.giphy.com/media/3o7qDSOvfaCO9b3MlO/giphy.gif)

### 🎯 Estratégia

**Por que escolhi esta arquitetura?**

Eu queria criar algo que demonstrasse expertise real, não apenas um "hello world" com Pandas. A arquitetura Data Lakehouse é o estado da arte atualmente, e implementar localmente mostra domínio tanto de conceitos quanto de execução prática.

**Trade-offs principais:**

1. **Complexidade vs Realismo:** Preferi 13 serviços reais a uma solução simplificada
2. **Recursos vs Funcionalidade:** Otimizei para rodar em 8GB RAM mantendo features enterprise
3. **Local vs Cloud:** Escolhi MinIO/Docker para eliminar custos e dependências externas
4. **Mock vs Real APIs:** Uso mock para demonstração, mas código preparado para APIs reais

**Decisões que me orgulho:**

- **Controle incremental por bairros:** Evita reprocessamento desnecessário
- **Rate limiting inteligente:** Respeita limites de API com backoff exponencial  
- **Configurações otimizadas:** 5-6GB RAM vs 12GB+ de setups tradicionais
- **Documentação pedagógica:** Explico o "porquê", não só o "como"

**O que eu faria diferente hoje:**

![Learning Never Stops](https://media.giphy.com/media/WoWm8YzFQJg5i/giphy.gif)

- Começaria com Kubernetes desde o início (Docker Compose tem limitações)
- Implementaria observabilidade desde o dia 1 (Prometheus + Grafana)
- Usaria Terraform para infraestrutura como código
- Adicionaria CI/CD com GitHub Actions

---

**Desenvolvido por [Danilo Vruck Rossetto Baeto](https://github.com/vruckdanilo)**

*"Transformando dados em insights, uma linha de código por vez."*

<div align="center">



![Thank You](https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExc3hod3Q0a2J5bHRsbWtvc3pzdnZjaWFoODQ4Z2ZxMnYzaHg2ZDg4aSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/uWlpPGquhGZNFzY90z/giphy.gif)

*Obrigado!*

</div>
