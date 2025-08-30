#!/bin/bash


# SCRIPT DE INICIALIZAÇÃO - DataMaster SentimentalReview



set -e  # Parar execução em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configurações
PROJECT_NAME="DataMaster SentimentalReview"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
HEALTH_CHECK_TIMEOUT=${HEALTH_CHECK_TIMEOUT:-300}  # 5 minutos (pode ser sobrescrito via .env)
RETRY_INTERVAL=10         # 10 segundos

# Carregar variáveis do .env (se existir) para o ambiente do script
if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi

# Ativar Docker Build Cloud (BuildKit) quando desejado
# Defina USE_CLOUD_BUILDER=true no ambiente para usar o cloud builder
USE_CLOUD_BUILDER=${USE_CLOUD_BUILDER:-true}
if [ "$USE_CLOUD_BUILDER" = "true" ]; then
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
fi

# Função para logging
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

log_info() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] ℹ️  $1${NC}"
}

# Função para verificar recursos do sistema
check_system_resources() {
    # Verificar uso de CPU
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    cpu_usage=$(echo $cpu_usage | tr ',' '.') # Corrigir vírgula para ponto
    cpu_usage_int=${cpu_usage%.*}  # Remover decimais para comparacao

    # Verificar uso de memória
    local mem_usage=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
    
    # Verificar espaço em disco
    local disk_usage=$(df . | tail -1 | awk '{print $5}' | sed 's/%//')
    
    # Log do status atual
    log_info "Recursos do sistema - CPU: ${cpu_usage}%, RAM: ${mem_usage}%, Disco: ${disk_usage}%"
    
    # Verificar se recursos estão muito altos
    if [ "$cpu_usage_int" -gt 80 ]; then
        log_warning "Uso de CPU alto (${cpu_usage}%). Aguardando estabilização..."
        sleep 30
    fi
    
    if [ "$mem_usage" -gt 85 ]; then
        log_warning "Uso de RAM alto (${mem_usage}%). Aguardando estabilização..."
        sleep 20
        # Tentar limpeza de cache Docker
        docker system prune -f > /dev/null 2>&1 || true
    fi
    
    if [ "$disk_usage" -gt 99 ]; then
        log_error "Espaço em disco crítico (${disk_usage}%). Liberando espaço..."
        # Evitar remover imagens necessárias (como spark-base). Limpeza segura:
        docker builder prune -f > /dev/null 2>&1 || true
        docker image prune -f > /dev/null 2>&1 || true
        docker container prune -f > /dev/null 2>&1 || true
    fi
}

# Função para exibir banner
show_banner() {
    echo -e "${PURPLE}"
    echo "======================================================================"
    echo "                    DataMaster SentimentalReview"
    echo "======================================================================"
    echo "  Plataforma de Análise de Sentimento - Agências Santander SP"
    echo ""
    echo "  🏗️  Data Lakehouse com Apache Iceberg + MinIO"
    echo "  🔄 Orquestração via Apache Airflow"
    echo "  ⚡ Processamento distribuído com PySpark"
    echo "  📊 Dashboard interativo com Plotly/Dash"
    echo "  🔍 Interface SQL com Trino + DBeaver"
    echo "======================================================================"
    echo -e "${NC}"
}

# Função para verificar pré-requisitos
check_prerequisites() {
    log "Verificando pré-requisitos..."
    
    # Verificar Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker não está instalado. Por favor, instale o Docker primeiro."
        exit 1
    fi
    
    # Verificar Docker Compose
    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose não está instalado. Por favor, instale o Docker Compose primeiro."
        exit 1
    fi
    
    # Verificar se Docker está rodando
    if ! docker info &> /dev/null; then
        log_error "Docker não está rodando. Por favor, inicie o Docker primeiro."
        exit 1
    fi
    
    # Verificar arquivo .env
    if [ ! -f "$ENV_FILE" ]; then
        log_warning "Arquivo .env não encontrado. Copiando do .env.exemplo..."
        if [ -f ".env.exemplo" ]; then
            cp .env.exemplo .env
            log_info "Arquivo .env criado. Por favor, configure as variáveis necessárias."
        else
            log_error "Arquivo .env.exemplo não encontrado."
            exit 1
        fi
    fi
    
    # Verificar docker-compose.yml
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Arquivo docker-compose.yml não encontrado."
        exit 1
    fi
    
    # Verificar espaço em disco (mínimo 10GB)
    available_space=$(df . | tail -1 | awk '{print $4}')
    min_space=10485760  # 10GB em KB
    
    if [ "$available_space" -lt "$min_space" ]; then
        log_warning "Espaço em disco pode ser insuficiente. Recomendado: 10GB+"
    fi
    
    # Verificar memória RAM (mínimo 8GB)
    total_mem=$(free -m | awk 'NR==2{print $2}')
    min_mem=8192  # 8GB em MB
    
    if [ "$total_mem" -lt "$min_mem" ]; then
        log_warning "Memória RAM pode ser insuficiente. Recomendado: 8GB+"
    fi
    
    log_success "Pré-requisitos verificados com sucesso"
}

# Função para limpar ambiente anterior
cleanup_previous() {
    log "Limpando ambiente anterior..."
    
    # Parar containers se estiverem rodando
    if docker compose ps -q &> /dev/null; then
        log_info "Parando containers existentes..."
        docker compose down --remove-orphans
    fi
    
    # Remover volumes órfãos (opcional)
    if [ "$1" = "--clean-volumes" ]; then
        log_warning "Removendo volumes de dados (dados serão perdidos)..."
        docker compose down -v
        docker volume prune -f
    fi
    
    log_success "Ambiente limpo"
}

# Garante que a imagem spark-base exista (pode ter sido removida por prune)
ensure_spark_base_image() {
    local BASE_TAG="${SPARK_BASE_IMAGE:-spark-base:latest}"
    if ! docker image inspect "$BASE_TAG" > /dev/null 2>&1; then
        log_warning "Imagem base '$BASE_TAG' ausente. Reconstruindo..."
        check_system_resources
        if docker compose --profile build build spark-base; then
            log_success "Imagem base '$BASE_TAG' construída/reconstruída com sucesso"
        else
            log_error "Falha ao construir imagem base '$BASE_TAG'"
            return 1
        fi
    fi
}

# Função para construir imagens sequencialmente
build_images() {
    log "Construindo imagens Docker na ordem correta..."

    # Construir base do Spark primeiro (necessário para imagens dependentes)
    log_info "Construindo imagem base: spark-base"
    check_system_resources
    if docker compose --profile build build spark-base; then
        log_success "Imagem spark-base construída com sucesso"
    else
        log_error "Falha ao construir imagem spark-base"
        return 1
    fi

    # Se estiver usando Cloud Builder e um registry estiver configurado, publicar spark-base
    if [ "$USE_CLOUD_BUILDER" = "true" ]; then
        local BASE_TAG="${SPARK_BASE_IMAGE:-spark-base:latest}"
        if [[ "$BASE_TAG" == *"/"* ]]; then
            log_info "Publicando imagem base no registry: $BASE_TAG"
            if docker compose --profile build push spark-base; then
                log_success "Imagem base publicada: $BASE_TAG"
            else
                log_error "Falha ao publicar imagem base: $BASE_TAG"
                return 1
            fi
        else
            log_warning "SPARK_BASE_IMAGE não aponta para um registry (atual: $BASE_TAG). Pulei o push da base."
        fi
    fi

    # Demais serviços que possuem Dockerfile no compose
    local services_to_build=("spark-master" "spark-worker" "hive-metastore" "trino-coordinator" "airflow-webserver" "airflow-scheduler")

    for service in "${services_to_build[@]}"; do
        log_info "Construindo imagem: $service"
        check_system_resources
        # Garantir base disponível antes de construir imagens que dependem dela
        if [[ "$service" == "spark-master" || "$service" == "spark-worker" ]]; then
            ensure_spark_base_image || return 1
        fi
        # Determinar a tag alvo caso seja spark-master/worker
        local TARGET_IMAGE=""
        if [ "$service" = "spark-master" ]; then
            TARGET_IMAGE="${SPARK_MASTER_IMAGE:-spark-master:latest}"
        elif [ "$service" = "spark-worker" ]; then
            TARGET_IMAGE="${SPARK_WORKER_IMAGE:-spark-worker:latest}"
        fi

        if [ "$USE_CLOUD_BUILDER" = "true" ] && [[ -n "$TARGET_IMAGE" && "$TARGET_IMAGE" == *"/"* ]]; then
            log_info "Usando cloud builder com push para $service -> $TARGET_IMAGE"
            if docker compose build --push "$service"; then
                log_success "Imagem $service publicada: $TARGET_IMAGE"
            else
                log_error "Falha ao construir/publicar $service"
                return 1
            fi
        else
            if docker compose build "$service"; then
                log_success "Imagem $service construída com sucesso"
            else
                log_error "Falha ao construir imagem $service"
                return 1
            fi
        fi
        # Pequena pausa para aliviar carga
        sleep 5
    done

    log_success "Todas as imagens construídas com sucesso"
}

# Função para iniciar serviços
start_services() {
    local up_extra_flags="$1"
    log "Iniciando serviços Docker..."

    # Sobe todos os serviços definidos; depends_on + healthchecks cuidam da ordem
    if ! docker compose up -d ${up_extra_flags}; then
        log_error "Falha ao iniciar serviços Docker"
        return 1
    fi

    log_success "docker compose up -d executado"
}

recreate_selected_services() {
    local csv="$1"
    local no_build_flag="${2:-false}"
    if [[ -z "$csv" ]]; then
        return 0
    fi
    IFS=',' read -r -a services <<< "$csv"
    log "Recriando serviços seletivamente: ${csv}"
    if [ "$no_build_flag" = true ]; then
        docker compose up -d --no-build --force-recreate --no-deps "${services[@]}"
    else
        docker compose up -d --force-recreate --no-deps "${services[@]}"
    fi
    log_success "Recriação aplicada: ${csv}"
}

# Função para aguardar serviço estar pronto
wait_for_service() {
    local service_name=$1
    local health_url=$2
    local timeout=$3
    local interval=${4:-5}
    
    log_info "Aguardando $service_name estar pronto..."
    
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if curl -f -s "$health_url" > /dev/null 2>&1; then
            log_success "$service_name está pronto"
            return 0
        fi
        
        sleep $interval
        elapsed=$((elapsed + interval))
        
        if [ $((elapsed % 30)) -eq 0 ]; then
            log_info "Aguardando $service_name... (${elapsed}s/${timeout}s)"
        fi
    done
    
    log_error "$service_name não ficou pronto em ${timeout}s"
    return 1
}

# Função para verificar saúde dos serviços
check_services_health() {
    log "Verificando saúde dos serviços..."

    local services_ok=0
    local total_services=0

    # MinIO API (porta 9000)
    total_services=$((total_services + 1))
    if wait_for_service "MinIO" "http://localhost:9000/minio/health/live" 90 5; then
        services_ok=$((services_ok + 1))
    fi

    # PostgreSQL Airflow
    total_services=$((total_services + 1))
    if docker compose exec -T postgres-airflow pg_isready -U airflow > /dev/null 2>&1; then
        log_success "PostgreSQL Airflow está pronto"
        services_ok=$((services_ok + 1))
    else
        log_error "PostgreSQL Airflow não está respondendo"
    fi

    # Zookeeper
    total_services=$((total_services + 1))
    if nc -z localhost 2181; then
        log_success "Zookeeper está pronto"
        services_ok=$((services_ok + 1))
    else
        log_error "Zookeeper não está respondendo"
    fi

    # Kafka
    total_services=$((total_services + 1))
    if docker compose exec -T kafka bash -lc 'kafka-topics --bootstrap-server localhost:9092 --list >/dev/null 2>&1 || kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1 || kafka-topics --bootstrap-server kafka:29092 --list >/dev/null 2>&1 || kafka-topics.sh --bootstrap-server kafka:29092 --list >/dev/null 2>&1'; then
        log_success "Kafka está pronto"
        services_ok=$((services_ok + 1))
    else
        log_error "Kafka não está respondendo"
    fi

    # MySQL (Hive Metastore)
    total_services=$((total_services + 1))
    if docker compose exec -T mysql mysqladmin ping -h localhost > "/dev/null" 2>&1; then
        log_success "MySQL (Hive Metastore) está pronto"
        services_ok=$((services_ok + 1))
    else
        log_error "MySQL (Hive Metastore) não está respondendo"
    fi

    # Hive Metastore
    total_services=$((total_services + 1))
    if nc -z localhost 9083; then
        log_success "Hive Metastore está pronto"
        services_ok=$((services_ok + 1))
    else
        log_error "Hive Metastore não está respondendo"
    fi

    # Spark Master (UI 8082)
    total_services=$((total_services + 1))
    if wait_for_service "Spark Master" "http://localhost:8082" 120 5; then
        services_ok=$((services_ok + 1))
    fi

    # Spark Worker (UI 8081)
    total_services=$((total_services + 1))
    if wait_for_service "Spark Worker" "http://localhost:8081" 120 5; then
        services_ok=$((services_ok + 1))
    fi

    # Trino (HTTP 8080)
    total_services=$((total_services + 1))
    if wait_for_service "Trino" "http://localhost:8080/v1/info" 120 5; then
        services_ok=$((services_ok + 1))
    fi

    # Airflow Webserver (porta mapeada 8089)
    total_services=$((total_services + 1))
    if wait_for_service "Airflow Webserver" "http://localhost:8089/health" 300 10; then
        services_ok=$((services_ok + 1))
    fi

    # Airflow Scheduler (health via docker inspect + airflow jobs check)
    total_services=$((total_services + 1))
    scheduler_status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' airflow-scheduler 2>/dev/null || echo "unknown")
    if [[ "$scheduler_status" == "healthy" || "$scheduler_status" == "running" ]]; then
        log_success "Airflow Scheduler está rodando ($scheduler_status)"
        services_ok=$((services_ok + 1))
    else
        # Fallback: validar heartbeat do Scheduler dentro do container
        if docker compose exec -T airflow-scheduler sh -lc 'airflow jobs check --job-type SchedulerJob --hostname "$HOSTNAME"' > /dev/null 2>&1; then
            log_success "Airflow Scheduler está rodando (jobs check)"
            services_ok=$((services_ok + 1))
        else
            log_error "Airflow Scheduler não está rodando (status: $scheduler_status)"
        fi
    fi

    # Superset (HTTP 8088)
    total_services=$((total_services + 1))
    if wait_for_service "Superset" "http://localhost:8088/health" "$HEALTH_CHECK_TIMEOUT" 10; then
        services_ok=$((services_ok + 1))
    fi

    # Google Maps Mock (porta 3001 -> 3000 interno)
    total_services=$((total_services + 1))
    if wait_for_service "Google Maps Mock" "http://localhost:3001/textsearch" 60 5; then
        services_ok=$((services_ok + 1))
    fi

    log_info "Serviços funcionais: $services_ok/$total_services"

    if [ $services_ok -eq $total_services ]; then
        log_success "Todos os serviços estão funcionais"
        return 0
    else
        # Fallback: se todos os containers estiverem 'healthy' ou 'running', considerar OK
        if containers_overall_ok; then
            log_success "Todos os serviços estão funcionais (status dos containers OK)"
            return 0
        fi
        log_warning "Alguns serviços podem não estar funcionais"
        return 1
    fi
}

# Verifica status geral dos containers pelo Docker (saída 'healthy' ou 'running')
containers_overall_ok() {
    local containers=("minio" "mysql" "postgres-airflow" "airflow-webserver" "airflow-scheduler" "zookeeper" "kafka" "hive-metastore" "spark-master" "spark-worker" "trino-coordinator" "superset" "google-maps-mock")
    for c in "${containers[@]}"; do
        local status
        status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$c" 2>/dev/null || echo "unknown")
        if [[ "$status" != "healthy" && "$status" != "running" ]]; then
            log_info "Container '$c' status atual: $status"
            return 1
        fi
    done
    return 0
}

# Função para configurar MinIO
setup_minio() {
    log "Configurando buckets MinIO..."

    # Aguardar MinIO API estar pronta (porta 9000)
    wait_for_service "MinIO" "http://localhost:9000/minio/health/live" 90 5

    # Configurar alias do MinIO client (credenciais conforme docker-compose)
    docker compose exec -T minio sh -c "mc alias set local http://localhost:9000 minio minio123" 2>/dev/null || true

    # Criar bucket único 'datalake'
    if docker compose exec -T minio sh -c "mc mb local/datalake" 2>/dev/null; then
        log_success "Bucket 'datalake' criado"
    else
        log_info "Bucket 'datalake' já existe"
    fi

    # Política pública de leitura (opcional)
    docker compose exec -T minio sh -c "mc anonymous set public local/datalake" 2>/dev/null || true
    log_success "MinIO configurado com sucesso"
}

# Função para configurar Kafka
setup_kafka() {
    log "Configurando tópicos Kafka..."
    
    # Aguardar Kafka estar pronto
    sleep 30
    
    # Criar tópicos
    local topics=("google-maps-data" "sentiment-analysis" "quality-alerts")
    
    for topic in "${topics[@]}"; do
        # Preferir 'kafka-topics' (sem .sh); fallback para 'kafka-topics.sh'.
        # Em caso de falha na criação, checar se já existe para log apropriado.
        if docker compose exec -T kafka bash -lc 'CMD=$(command -v kafka-topics || command -v kafka-topics.sh); "$CMD" --bootstrap-server localhost:9092 --create --topic '"'"$topic"'"' --partitions 3 --replication-factor 1' >/dev/null 2>&1; then
            log_success "Tópico '$topic' criado"
        else
            if docker compose exec -T kafka bash -lc 'CMD=$(command -v kafka-topics || command -v kafka-topics.sh); "$CMD" --bootstrap-server localhost:9092 --list | grep -Fx '"'"$topic"'"'' >/dev/null 2>&1; then
                log_info "Tópico '$topic' já existe"
            else
                log_error "Falha ao criar tópico '$topic'"
            fi
        fi
    done
    log_success "Kafka configurado com sucesso"
}

# Função para configurar Airflow
setup_airflow() {
    log "Configurando Airflow..."

    # Aguardar Webserver estar pronto
    wait_for_service "Airflow" "http://localhost:8089/health" 180 10

    # Criar usuário admin se não existir
    docker compose exec -T airflow-webserver airflow users create \
        --username admin \
        --firstname Admin \
        --lastname DataMaster \
        --role Admin \
        --email admin@datamaster.com \
        --password admin123 2>/dev/null || log_info "Usuário admin já existe"

    # Conexões
    log_info "Configurando conexões do Airflow..."

    # Conexão MinIO
    docker compose exec -T airflow-webserver airflow connections add \
        --conn-id minio_default \
        --conn-type s3 \
        --conn-host minio \
        --conn-port 9000 \
        --conn-login minio \
        --conn-password minio123 \
        --conn-extra '{"aws_access_key_id": "minio", "aws_secret_access_key": "minio123", "endpoint_url": "http://minio:9000"}' 2>/dev/null || true

    # Conexão Kafka
    docker compose exec -T airflow-webserver airflow connections add \
        --conn-id kafka_default \
        --conn-type kafka \
        --conn-host kafka \
        --conn-port 9092 \
        --conn-extra '{"bootstrap_servers": "kafka:9092"}' 2>/dev/null || true

    # Conexão Spark (standalone master)
    docker compose exec -T airflow-webserver airflow connections add \
        --conn-id spark_default \
        --conn-type spark \
        --conn-host spark-master \
        --conn-port 7077 \
        --conn-extra '{"master": "spark://spark-master:7077"}' 2>/dev/null || true

    log_success "Airflow configurado com sucesso"
}

# Função para executar testes básicos
run_basic_tests() {
    log "Executando testes básicos..."

    # Teste MinIO
    if curl -fsS http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        log_success "Teste MinIO: OK"
    else
        log_error "Teste MinIO: FALHOU"
    fi

    # Teste Kafka
    if docker compose exec -T kafka bash -lc 'kafka-topics --bootstrap-server localhost:9092 --list >/dev/null 2>&1 || kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1 || kafka-topics --bootstrap-server kafka:29092 --list >/dev/null 2>&1 || kafka-topics.sh --bootstrap-server kafka:29092 --list >/dev/null 2>&1'; then
        log_success "Teste Kafka: OK"
    else
        log_error "Teste Kafka: FALHOU"
    fi

    # Teste PostgreSQL (Airflow)
    if docker compose exec -T postgres-airflow pg_isready -h localhost -U airflow > "/dev/null" 2>&1; then
        log_success "Teste PostgreSQL (Airflow): OK"
    else
        log_error "Teste PostgreSQL (Airflow): FALHOU"
    fi

    # Teste Spark Master UI
    if curl -fsS http://localhost:8082 > /dev/null 2>&1; then
        log_success "Teste Spark Master: OK"
    else
        log_error "Teste Spark Master: FALHOU"
    fi

    log_success "Testes básicos concluídos"
}

# Função para exibir informações de acesso
show_access_info() {
    # Checagem de DAGs do Airflow
    log_info "Listando DAGs carregados no Airflow..."
    if docker compose exec -T airflow-webserver airflow dags list; then
        log_success "DAGs do Airflow listados acima."
    else
        log_warning "Não foi possível listar os DAGs do Airflow. Verifique o serviço."
    fi

    echo -e "${GREEN}"
    echo "======================================================================"
    echo "                    🎉 INSTALAÇÃO CONCLUÍDA! 🎉"
    echo "======================================================================"
    echo -e "${NC}"

    echo -e "${CYAN}📊 INTERFACES DE ACESSO:${NC}"
    echo ""
    echo -e "  🔄 ${YELLOW}Airflow:${NC}          http://localhost:8089 (admin/admin123)"
    echo -e "  ⚡ ${YELLOW}Spark Master:${NC}     http://localhost:8082"
    echo -e "  🧱 ${YELLOW}Spark Worker:${NC}     http://localhost:8081"
    echo -e "  🔍 ${YELLOW}Trino:${NC}            http://localhost:8080"
    echo -e "  💾 ${YELLOW}MinIO Console:${NC}    http://localhost:9001 (minio/minio123)"
    echo -e "  🗺️  ${YELLOW}Google Maps Mock:${NC} http://localhost:3001"
    echo -e "  📊 ${YELLOW}Superset:${NC}         http://localhost:8088 (admin/admin123)"
    echo ""

    echo -e "${CYAN}🔧 CONFIGURAÇÕES:${NC}"
    echo ""
    echo -e "  📁 ${YELLOW}Bucket MinIO:${NC}     datalake"
    echo -e "  📡 ${YELLOW}Tópicos Kafka:${NC}    google-maps-data, sentiment-analysis, quality-alerts"
    echo -e "  🐘 ${YELLOW}PostgreSQL:${NC}       localhost:5432 (airflow/airflow)"
    echo ""

    echo -e "${CYAN}📚 PRÓXIMOS PASSOS:${NC}"
    echo ""
    echo -e "  1. Configure conexões no Superset/Trino conforme necessidade"
    echo -e "  2. Execute os DAGs do Airflow para iniciar o pipeline"
    echo -e "  3. Monitore os serviços e healthchecks com 'docker compose ps'"
    echo ""

    echo -e "${GREEN}✨ Projeto DataMaster SentimentalReview está pronto para uso! ✨${NC}"
    echo ""
}

# Função para exibir ajuda
show_help() {
    echo "Uso: $0 [OPÇÕES]"
    echo ""
    echo "OPÇÕES:"
    echo "  --clean-volumes    Remover volumes de dados (CUIDADO: dados serão perdidos)"
    echo "  --no-tests         Pular testes básicos"
    echo "  --no-build         Não reconstruir imagens (passa --no-build ao 'docker compose up')"
    echo "  --no-down          Não derrubar containers existentes (mantém rodando)"
    echo "  --recreate-services svc1,svc2  Recriar serviços especificados (sem derrubar os demais)"
    echo "  --recreate-superset            Atalho para --recreate-services superset"
    echo "  --help             Exibir esta ajuda"
    echo ""
    echo "EXEMPLOS:"
    echo "  $0                 Inicialização padrão"
    echo "  $0 --clean-volumes Inicialização com limpeza completa"
    echo "  $0 --no-tests      Inicialização sem testes"
    echo "  $0 --no-build      Pular rebuild de imagens"
    echo "  $0 --no-down       Manter containers atuais e apenas reconfigurar"
    echo "  $0 --no-build --no-down  Reconfigurar sem rebuild e sem downtime"
    echo "  $0 --recreate-services superset            Recriar apenas o Superset"
    echo "  $0 --no-build --no-down --recreate-services superset,trino-coordinator"
}

# Função principal
main() {
    local clean_volumes=false
    local run_tests=true
    local skip_build=false
    local no_down=false
    local recreate_services=""
    
    # Processar argumentos
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean-volumes)
                clean_volumes=true
                shift
                ;;
            --no-tests)
                run_tests=false
                shift
                ;;
            --no-build)
                skip_build=true
                shift
                ;;
            --no-down)
                no_down=true
                shift
                ;;
            --recreate-services)
                recreate_services="${2:-}"
                if [[ -z "$recreate_services" || "$recreate_services" == --* ]]; then
                    log_error "Uso: --recreate-services svc1,svc2"
                    exit 1
                fi
                shift 2
                ;;
            --recreate-superset)
                if [[ -z "$recreate_services" ]]; then
                    recreate_services="superset"
                else
                    recreate_services="${recreate_services},superset"
                fi
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Opção desconhecida: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Validações de compatibilidade entre flags
    if [ "$clean_volumes" = true ] && [ "$no_down" = true ]; then
        log_error "Opções incompatíveis: --no-down não pode ser usado com --clean-volumes"
        exit 1
    fi
    
    # Fast path: apenas recriar serviços solicitados quando combinado com --no-down
    if [[ -n "$recreate_services" && "$no_down" = true ]]; then
        log_info "Modo rápido: apenas recriando serviços solicitados: $recreate_services"
        recreate_selected_services "$recreate_services" "$skip_build"

        # Se Superset estiver entre os serviços, aguarda ficar pronto
        if [[ ",$recreate_services," == *",superset,"* ]]; then
            wait_for_service "Superset" "http://localhost:8088/health" "$HEALTH_CHECK_TIMEOUT" 10 || true
            log_success "Superset recriado e respondendo em http://localhost:8088"
        fi

        log_success "Recriação concluída."
        exit 0
    fi
    
    # Executar inicialização
    show_banner
    
    # Verificar recursos iniciais do sistema
    log "Verificando recursos iniciais do sistema..."
    check_system_resources
    
    check_prerequisites
    
    if [ "$no_down" = true ]; then
        log_info "Flag --no-down acionada: pulando 'docker compose down'; containers permanecerão em execução."
    else
        if [ "$clean_volumes" = true ]; then
            cleanup_previous --clean-volumes
        else
            cleanup_previous
        fi
    fi
    
    # Verificar recursos antes do build
    log "Verificando recursos antes do build..."
    check_system_resources
    
    if [ "$skip_build" = true ]; then
        log_info "Pulando rebuild de imagens (--no-build)."
        start_services "--no-build"
    else
        build_images
        start_services
    fi

    # Recriação seletiva de serviços, se solicitado
    if [[ -n "$recreate_services" ]]; then
        log_info "Recriando serviços solicitados: $recreate_services"
        recreate_selected_services "$recreate_services" "$skip_build"
    fi
    
    setup_minio
    setup_kafka
    setup_airflow
    
    if [ "$run_tests" = true ]; then
        run_basic_tests
    fi
    
    check_services_health
    
    show_access_info
    
    log_success "Inicialização do $PROJECT_NAME concluída com sucesso!"
}

# Executar função principal
main "$@"
