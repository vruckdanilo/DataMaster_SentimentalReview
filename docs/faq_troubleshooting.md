# ❓ FAQ e Troubleshooting - DataMaster SentimentalReview

![Troubleshooting](https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZGprYzJkYXl3a3RxNG85MDhxa3p4ZTV0bnZzenRoMTdqdm5rcG03dyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/7K3p2z8Hh9QOI/giphy.gif)

Este documento consolida as perguntas mais frequentes e soluções para problemas comuns encontrados durante instalação, configuração e operação do sistema.

---

## 📋 Índice

- [🚀 Instalação e Setup](#-instalação-e-setup)
- [🐳 Problemas com Docker](#-problemas-com-docker)
- [⚡ Issues do Spark](#-issues-do-spark)
- [🔄 Problemas do Airflow](#-problemas-do-airflow)
- [📊 Superset e Visualização](#-superset-e-visualização)
- [🔧 Performance e Recursos](#-performance-e-recursos)
- [📁 Dados e Pipeline](#-dados-e-pipeline)

---

## 🚀 Instalação e Setup

![Setup Process](https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGdyam40ZTRqbDVhM3N6azh0ZWt2cDJoemtndXF0NGpxZnlhcnFuayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/AqV8uSb8ptxyo7Wyog/giphy.gif)

### Q: O script start.sh falha com "Permission denied"
**A:** Torne o script executável:
```bash
chmod +x [`scripts/start.sh`](../scripts/start.sh)
[`./scripts/start.sh`](../scripts/start.sh)
```

### Q: Erro "Port already in use" durante inicialização
**A:** Verifique processos usando as portas:
```bash
# Verificar portas ocupadas
sudo lsof -i :8089  # Airflow
sudo lsof -i :8088  # Superset
sudo lsof -i :8080  # Trino
sudo lsof -i :8082  # Spark Master
sudo lsof -i :8081  # Spark Worker

# Parar processos conflitantes
sudo systemctl stop apache2
sudo systemctl stop nginx

# Ou matar processo específico
sudo kill -9 $(sudo lsof -t -i:8089)
sudo kill -9 $(sudo lsof -t -i:8088)
sudo kill -9 $(sudo lsof -t -i:8080)
```

### Q: Containers ficam "unhealthy" após inicialização
**A:** Aguarde mais tempo (primeira inicialização pode levar 10-15 min):
```bash
# Verificar logs específicos
docker compose logs -f [service-name]

# Reiniciar serviço específico
docker compose restart [service-name]

# Verificar recursos disponíveis
docker stats
```

### Q: Erro "No space left on device"
**A:** Limpe imagens e volumes não utilizados:
```bash
# Limpar sistema Docker
docker system prune -f

# Limpar volumes órfãos
docker volume prune -f

# Verificar espaço
df -h
docker system df
```

---

## 🐳 Problemas com Docker

![Docker Issues](https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExcXZwOHhocWtycHk1bzZ1bDJwaDZ0NGYzZnJwdGtrczR5Z2c1OTlicCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xVurSXSjNiifP8qLXy/giphy.gif)

### Q: "Cannot connect to Docker daemon"
**A:** Verifique se Docker está rodando:
```bash
# Verificar status
sudo systemctl status docker

# Iniciar Docker
sudo systemctl start docker

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
newgrp docker
```

### Q: Containers crasham por falta de memória
**A:** Aumente recursos no Docker Desktop:
```bash
# Docker Desktop: Settings > Resources > Memory > 8GB+

# Ou reduza configurações no [`.env`](../.env)
SPARK_DRIVER_MEMORY=256m
SPARK_EXECUTOR_MEMORY=256m
# (Valores atuais: 512m cada)
```

### Q: Build das imagens falha
**A:** Limpe cache e rebuilde:
```bash
# Limpar cache de build
docker builder prune -f

# Rebuild forçado
docker compose build --no-cache

# Verificar espaço em disco
df -h
```

### Q: Rede Docker com problemas de conectividade
**A:** Recrie a rede:
```bash
# Parar containers
docker compose down

# Remover rede
docker network rm datamaster_sentimentalreview_data_network

# Recriar tudo
docker compose up -d
```

---

## ⚡ Issues do Spark



### Q: Spark jobs falham com "Error code is: 1"
**A:** Verifique mapeamento de volumes e caminhos:
```bash
# Verificar se arquivos existem no container
docker compose exec spark-master ls -la /opt/bitnami/spark/jobs/

# Verificar logs detalhados
docker compose logs spark-master | grep -i error

# Testar job simples
docker compose exec spark-master spark-submit --version
```

### Q: "java.net.UnknownHostException: hive-metastore"
**A:** Use HadoopCatalog em vez de HiveCatalog:
```python
# Em jobs Spark, configure:
.config("spark.sql.catalog.lakehouse.type", "hadoop")
# Remover: .config("spark.sql.catalog.lakehouse.uri", "thrift://hive-metastore:9083")
```

### Q: Spark Thrift Server não inicia na porta 10000
**A:** Verifique configurações e dependências:
```bash
# Verificar se porta está aberta
nc -zv localhost 10000

# Verificar logs do Thrift Server
docker compose logs spark-master | grep -i thrift

# Testar conectividade interna
docker compose exec superset ping spark-master
```

### Q: "OutOfMemoryError" em jobs Spark
**A:** Ajuste configurações de memória:
```bash
# No [`.env`](../.env), aumente:
SPARK_DRIVER_MEMORY=1g
SPARK_EXECUTOR_MEMORY=1g
# (Valores atuais: 512m cada)

# Ou no job Spark:
.config("spark.driver.memory", "1g")
.config("spark.executor.memory", "1g")
```

---

## 🔄 Problemas do Airflow



### Q: DAGs não aparecem na interface
**A:** Verifique diretório e permissões:
```bash
# Verificar arquivos DAG
docker compose exec airflow-webserver ls -la /opt/airflow/dags/

# Verificar logs do scheduler
docker compose logs airflow-scheduler | grep -i dag

# Forçar refresh
docker compose exec airflow-webserver airflow dags list-import-errors
```

### Q: "No module named 'scripts'" em DAGs
**A:** Verifique mapeamento de volumes e __init__.py:
```bash
# Verificar mapeamento
docker compose exec airflow-webserver ls -la /opt/airflow/scripts/

# Criar __init__.py se não existir
touch [`mnt/airflow/scripts/__init__.py`](../mnt/airflow/scripts/__init__.py)

# Reiniciar scheduler
docker compose restart airflow-scheduler
```

### Q: Tasks ficam em estado "running" indefinidamente
**A:** Verifique recursos e reinicie:
```bash
# Verificar tasks ativas
docker compose exec airflow-webserver airflow tasks list dag_id

# Matar tasks travadas
docker compose exec airflow-webserver airflow tasks clear dag_id

# Reiniciar workers
docker compose restart airflow-scheduler
```

### Q: Conexões com outros serviços falham
**A:** Use nomes de serviços Docker, não localhost:
```python
# ✅ Correto
MINIO_ENDPOINT = "minio:9000"
KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"

# ❌ Incorreto
MINIO_ENDPOINT = "localhost:9000"
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
```

---

## 📊 Superset e Visualização



### Q: Erro 405 "Method Not Allowed" no Superset
**A:** Desabilite CSRF temporariamente:
```python
# Em superset_config.py
WTF_CSRF_ENABLED = False
ENABLE_PROXY_FIX = True
```

### Q: "Could not connect to any of [('spark-master', 10000)]"
**A:** Verifique conectividade e configuração:
```bash
# Testar conectividade
docker compose exec superset ping spark-master

# Verificar se Thrift Server está rodando
docker compose exec spark-master netstat -tlnp | grep 10000

# Usar URI alternativa
# hive://localhost:10000/default (se acessando externamente)
```

### Q: Drivers Trino/Hive não encontrados
**A:** Instale dependências no container:
```bash
# Entrar no container Superset
docker compose exec superset bash

# Instalar drivers
pip install pyhive thrift thrift-sasl sqlalchemy-trino

# Reiniciar Superset
docker compose restart superset
```

### Q: Dashboards não carregam dados
**A:** Verifique conexão e permissões:
```bash
# Testar conexão SQL
docker compose exec superset superset db upgrade

# Verificar datasets (comando não existe no Superset)
# Use a interface web em http://localhost:8088 > Data > Datasets

# Testar query manual no SQL Lab
```

---

## 🔧 Performance e Recursos

![Performance Tuning](https://media.giphy.com/media/3o7abB06u9bNzA8lu8/giphy.gif)

### Q: Sistema muito lento
**A:** Otimize configurações de recursos:
```bash
# Verificar uso atual
docker stats

# Aumentar recursos Docker Desktop
# Settings > Resources > Memory: 8GB+, CPUs: 4+

# Otimizar configurações Spark
SPARK_DRIVER_MEMORY=512m
SPARK_EXECUTOR_MEMORY=512m
SPARK_DRIVER_CORES=1
SPARK_EXECUTOR_CORES=1
```

### Q: MinIO com alta latência
**A:** Verifique configurações de rede e disco:
```bash
# Testar velocidade de disco
docker compose exec minio dd if=/dev/zero of=/data/test bs=1M count=100

# Verificar logs MinIO
docker compose logs minio | grep -i error

# Otimizar configurações
# Usar SSD se possível
# Aumentar MINIO_BROWSER_REDIRECT_URL se necessário
```

### Q: Kafka com lag alto
**A:** Ajuste configurações de throughput:
```bash
# Verificar tópicos
docker compose exec kafka kafka-topics --bootstrap-server kafka:29092 --list

# Verificar consumer lag
docker compose exec kafka kafka-consumer-groups --bootstrap-server kafka:29092 --describe --all-groups

# Otimizar configurações no [`docker-compose.yml`](../docker-compose.yml)
# (Nota: estas variáveis não estão configuradas no projeto atual)
# Para ajustar partições, use comandos kafka-topics diretamente
```

---

## 📁 Dados e Pipeline



### Q: Pipeline falha na camada Bronze
**A:** Verifique dados de entrada e schema:
```bash
# Verificar dados na Landing
docker compose exec minio mc ls local/datalake/landing/

# Verificar logs do job
docker compose logs spark-master | grep -i bronze

# Testar leitura manual
docker compose exec spark-master pyspark
# >>> df = spark.read.json("s3a://datalake/landing/")
# >>> df.show()
```

### Q: Análise de sentimentos falha
**A:** Verifique modelos NLP e dependências:
```bash
# O projeto usa análise de sentimento baseada em dicionário, não Hugging Face
# Verificar se palavras-chave estão carregadas corretamente
docker compose exec spark-master python -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.getOrCreate()
print('Spark session criada com sucesso')
"

# Verificar logs detalhados
docker compose logs spark-master | grep -i nlp
```

### Q: Dados não aparecem no Trino
**A:** Verifique catálogo e metastore:
```bash
# Conectar ao Trino CLI
docker compose exec trino-coordinator trino --server localhost:8080 --catalog delta --schema default

# Listar catálogos
SHOW CATALOGS;

# Listar schemas
SHOW SCHEMAS FROM delta;

# Verificar tabelas
SHOW TABLES FROM delta.default;
```

### Q: Controle incremental não funciona
**A:** Verifique arquivo de controle:
```bash
# Verificar arquivo de controle
docker compose exec airflow-webserver cat /opt/airflow/raw_data/controle_progresso_bairros.json

# Verificar permissões
docker compose exec airflow-webserver ls -la /opt/airflow/raw_data/

# Resetar controle se necessário
docker compose exec airflow-webserver rm /opt/airflow/raw_data/controle_progresso_bairros.json
```

---

## 🆘 Comandos de Emergência

![Emergency Commands](https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3lqZzdpbDZkczF3MWw3emtrcDFpamw2MDh2ZDdjNWVnYXB1dGJwdCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/phJ6eMRFYI6CQ/giphy.gif)

### Reset Completo do Sistema
```bash
# CUIDADO: Remove todos os dados
docker compose down -v
docker system prune -f
docker volume prune -f
[`./scripts/start.sh`](../scripts/start.sh) --clean-volumes
```

### Backup de Dados Críticos
```bash
# Backup configurações Airflow
docker compose exec airflow-webserver tar -czf /tmp/airflow_backup.tar.gz /opt/airflow/dags /opt/airflow/scripts

# Backup dados MinIO
docker compose exec minio mc mirror local/datalake /tmp/minio_backup/

# Copiar backups para host
docker cp $(docker compose ps -q airflow-webserver):/tmp/airflow_backup.tar.gz ./backups/
```

### Logs de Debugging Completo
```bash
# Coletar todos os logs
mkdir -p debug_logs
docker compose logs > debug_logs/all_services.log
docker compose ps > debug_logs/containers_status.txt
docker stats --no-stream > debug_logs/resources_usage.txt
docker system df > debug_logs/disk_usage.txt
```

### Teste de Conectividade Completo
```bash
#!/bin/bash
# Script de teste completo
echo "=== TESTE DE CONECTIVIDADE ==="

services=("airflow-webserver:8089" "superset:8088" "minio:9001" "trino-coordinator:8080" "spark-master:8082" "spark-worker:8081")

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if curl -f -s "http://localhost:$port" > /dev/null; then
        echo "✅ $name ($port): OK"
    else
        echo "❌ $name ($port): FALHA"
    fi
done
```

---



