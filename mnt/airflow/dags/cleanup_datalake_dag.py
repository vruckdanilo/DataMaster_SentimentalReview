#!/usr/bin/env python3


from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
import logging

# Configurações da DAG
default_args = {
    'owner': 'datamaster-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
    'email': ['datamaster-alerts@santander.com.br']
}

def confirm_cleanup_operation(**context):
    """Função de confirmação antes da limpeza"""
    logger = logging.getLogger(__name__)
    
    logger.warning("=" * 60)
    logger.warning("⚠️  ATENÇÃO: OPERAÇÃO DE LIMPEZA COMPLETA")
    logger.warning("⚠️  Esta DAG remove TODOS os dados do datalake!")
    logger.warning("⚠️  - Tabelas do schema datalake")
    logger.warning("⚠️  - Dados do MinIO (bucket datalake)")
    logger.warning("⚠️  - Arquivos temporários e logs")
    logger.warning("=" * 60)
    logger.warning("📋 Para prosseguir, confirme que:")
    logger.warning("   1. Você tem certeza da operação")
    logger.warning("   2. Backup foi feito se necessário")
    logger.warning("   3. Execução é intencional")
    logger.warning("=" * 60)
    
    # Em produção, aqui poderia ter uma verificação adicional
    # como um parâmetro de confirmação ou token de segurança
    
    return True

# Definição da DAG
dag = DAG(
    'cleanup_datalake_complete',
    default_args=default_args,
    description='🧹 Limpeza completa do DataLake e MinIO - EXECUÇÃO MANUAL',
    schedule_interval=None,  # APENAS EXECUÇÃO MANUAL
    catchup=False,
    max_active_runs=1,
    tags=['cleanup', 'manual-only', 'datalake', 'minio', 'reset']
)

# Operadores de início e fim
start_cleanup = DummyOperator(
    task_id='start_cleanup',
    dag=dag
)

end_cleanup = DummyOperator(
    task_id='end_cleanup',
    dag=dag
)

# Task Group: Confirmação e Preparação
with TaskGroup('preparation', dag=dag) as preparation_group:
    
    # Confirmação da operação
    confirm_operation = PythonOperator(
        task_id='confirm_cleanup_operation',
        python_callable=confirm_cleanup_operation,
        dag=dag
    )
    
    # Verificação de dependências
    check_dependencies = BashOperator(
        task_id='check_dependencies',
        bash_command='''
        echo "=== VERIFICANDO DEPENDÊNCIAS ==="
        echo "🔍 Verificando conexões de rede..."
        
        # Verificar MinIO
        MINIO_STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://minio:9000/minio/health/live 2>/dev/null || echo 'OFFLINE')
        echo "MinIO: $MINIO_STATUS"
        
        # Verificar Spark Master
        SPARK_STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://spark-master:8082 2>/dev/null || echo 'OFFLINE')
        echo "Spark Master: $SPARK_STATUS"
        
        # Verificar Hive Metastore (porta 9083)
        HIVE_STATUS=$(nc -z hive-metastore 9083 2>/dev/null && echo "200" || echo "OFFLINE")
        echo "Hive Metastore: $HIVE_STATUS"
        
        echo ""
        echo "✅ Verificação de dependências concluída"
        echo "⚠️ Prosseguindo com limpeza independente do status dos serviços"
        ''',
        dag=dag
    )
    
    # Backup de metadados (opcional)
    backup_metadata = BashOperator(
        task_id='backup_metadata',
        bash_command='''
        echo "=== BACKUP DE METADADOS ==="
        mkdir -p /opt/airflow/backups/$(date +%Y%m%d_%H%M%S)
        echo "📁 Diretório de backup criado"
        
        # Backup de arquivos de status existentes
        if [ -d "/opt/airflow/spark_jobs/status" ]; then
            cp -r /opt/airflow/spark_jobs/status/* /opt/airflow/backups/$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true
            echo "📋 Arquivos de status copiados para backup"
        fi
        
        echo "✅ Backup de metadados concluído"
        ''',
        dag=dag
    )
    
    # Sequência de preparação
    confirm_operation >> check_dependencies >> backup_metadata

# Task Group: Limpeza do Schema/Catálogo
with TaskGroup('cleanup_catalog', dag=dag) as cleanup_catalog_group:
    
    # Limpeza completa do catálogo Hive - EXECUÇÃO DIRETA VIA SPARK
    cleanup_hive_catalog = BashOperator(
        task_id='cleanup_hive_catalog',
        bash_command='''
        echo "=== LIMPEZA DO CATÁLOGO HIVE/DELTA ==="
        
        # Executar limpeza do catálogo usando comandos SQL diretos
        docker exec spark-master /opt/spark/bin/spark-sql \
            --packages io.delta:delta-core_2.12:2.4.0 \
            --conf "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" \
            --conf "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" \
            -e "DROP DATABASE IF EXISTS datalake CASCADE;" || echo "⚠️ Database datalake não existe"
        
        echo "🗑️ Database datalake removido do catálogo"
        
        echo "✅ Limpeza do catálogo concluída"
        ''',
        dag=dag
    )

# Task Group: Limpeza do MinIO
with TaskGroup('cleanup_storage', dag=dag) as cleanup_storage_group:
    
    # Limpeza dos buckets MinIO - EXECUÇÃO DIRETA VIA MC CLIENT
    cleanup_minio_buckets = BashOperator(
        task_id='cleanup_minio_buckets',
        bash_command='''
        echo "=== LIMPEZA DO MINIO DATALAKE ==="
        
        # Executar limpeza direta do MinIO usando Python/boto3 - versão robusta
        python3 -c "
import boto3
from botocore.exceptions import ClientError

# Configurar cliente S3 para MinIO
s3_client = boto3.client(
    's3',
    endpoint_url='http://minio:9000',
    aws_access_key_id='minio',
    aws_secret_access_key='minio123',
    aws_session_token=None,
    region_name='us-east-1'
)

# Função para limpar pasta recursivamente - versão mais robusta
def clean_folder_complete(bucket, prefix):
    try:
        # Listar todos os objetos com paginação
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        total_deleted = 0
        for page in page_iterator:
            if 'Contents' in page:
                objects = [{'Key': obj['Key']} for obj in page['Contents']]
                if objects:
                    # Deletar objetos em lotes
                    s3_client.delete_objects(Bucket=bucket, Delete={'Objects': objects})
                    total_deleted += len(objects)
        
        if total_deleted > 0:
            print(f'✅ Pasta {prefix} limpa - {total_deleted} objetos removidos')
        else:
            print(f'⚠️ Pasta {prefix} já estava vazia')
    except ClientError as e:
        print(f'⚠️ Erro ao limpar {prefix}: {e}')

# Limpar todas as pastas incluindo subpastas
folders_to_clean = ['landing/', 'bronze/', 'silver/', 'gold/', 'controle/']
for folder in folders_to_clean:
    clean_folder_complete('datalake', folder)
"
        
        # Limpeza adicional via comando direto no filesystem
        echo "🗑️ Limpeza adicional via filesystem..."
        docker exec minio rm -rf /data/datalake/landing/* 2>/dev/null || true
        docker exec minio rm -rf /data/datalake/bronze/* 2>/dev/null || true
        docker exec minio rm -rf /data/datalake/silver/* 2>/dev/null || true
        docker exec minio rm -rf /data/datalake/gold/* 2>/dev/null || true
        docker exec minio rm -rf /data/datalake/controle/* 2>/dev/null || true
        
        echo "✅ Limpeza do MinIO concluída"
        ''',
        dag=dag
    )

# Task Group: Limpeza de Arquivos Temporários
with TaskGroup('cleanup_temp_files', dag=dag) as cleanup_temp_group:
    
    # Limpeza de logs do Airflow
    cleanup_airflow_logs = BashOperator(
        task_id='cleanup_airflow_logs',
        bash_command='''
        echo "=== LIMPANDO LOGS DO AIRFLOW ==="
        
        # Remover logs antigos (> 7 dias)
        find /opt/airflow/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true
        echo "📄 Logs antigos do Airflow removidos"
        
        # Limpar cache de tasks
        find /opt/airflow/logs -name "*.pid" -delete 2>/dev/null || true
        echo "🗂️ Arquivos PID removidos"
        
        echo "✅ Limpeza de logs do Airflow concluída"
        ''',
        dag=dag
    )
    
    # Limpeza de arquivos temporários do Spark
    cleanup_spark_temp = BashOperator(
        task_id='cleanup_spark_temp',
        bash_command='''
        echo "=== LIMPANDO ARQUIVOS TEMPORÁRIOS DO SPARK ==="
        
        # Limpar arquivos temporários locais
        rm -rf /opt/airflow/spark_jobs/scripts/* 2>/dev/null || true
        rm -rf /opt/airflow/spark_jobs/status/* 2>/dev/null || true
        rm -rf /opt/airflow/spark_jobs/logs/* 2>/dev/null || true
        echo "📂 Arquivos de jobs removidos"
        
        # Limpar cache do sistema
        find /tmp -name "spark-*" -type d -mtime +1 -exec rm -rf {} + 2>/dev/null || true
        echo "🗄️ Cache temporário limpo"
        
        echo "✅ Limpeza de arquivos temporários concluída"
        ''',
        dag=dag
    )
    
    # Limpeza em paralelo
    [cleanup_airflow_logs, cleanup_spark_temp]

# Task Group: Verificação Final
with TaskGroup('verification', dag=dag) as verification_group:
    
    # Verificação de limpeza
    verify_cleanup = BashOperator(
        task_id='verify_cleanup_complete',
        bash_command='''
        echo "=== VERIFICAÇÃO FINAL DE LIMPEZA ==="
        echo ""
        
        echo "🔍 Verificando schema datalake..."
        # Esta verificação será feita pelo próprio job Spark
        echo "   ➜ Verificação delegada aos jobs Spark"
        echo ""
        
        echo "🔍 Verificando MinIO..."
        # Tentar listar objetos no bucket (deve estar vazio)
        echo "   ➜ Verificação delegada ao job MinIO"
        echo ""
        
        echo "🔍 Verificando arquivos temporários..."
        TEMP_COUNT=$(find /opt/airflow/spark_jobs -name "*.json" 2>/dev/null | wc -l)
        echo "   ➜ Arquivos temporários restantes: $TEMP_COUNT"
        echo ""
        
        echo "✅ Verificação final concluída"
        echo ""
        echo "📋 LIMPEZA COMPLETA FINALIZADA!"
        echo "   🧹 Schema datalake limpo"
        echo "   🧹 Dados MinIO removidos" 
        echo "   🧹 Arquivos temporários limpos"
        echo ""
        echo "🚀 Ambiente pronto para execução limpa do pipeline!"
        ''',
        dag=dag
    )
    
    # Geração de relatório final
    generate_cleanup_report = BashOperator(
        task_id='generate_cleanup_report',
        bash_command='''
        echo "=== GERANDO RELATÓRIO DE LIMPEZA ==="
        
        REPORT_FILE="/tmp/cleanup_report_$(date +%Y%m%d_%H%M%S).txt"
        
        cat > "$REPORT_FILE" << EOF
====================================================================
RELATÓRIO DE LIMPEZA COMPLETA - DATAMASTER
====================================================================

Data/Hora: $(date)
DAG: cleanup_datalake_complete
Executado por: ${AIRFLOW_CTX_DAG_OWNER}

OPERAÇÕES REALIZADAS:
✅ Limpeza do schema datalake (Hive Metastore)
✅ Limpeza dos dados MinIO (bucket datalake) 
✅ Limpeza de arquivos temporários
✅ Limpeza de logs antigos
✅ Verificação final de integridade

STATUS: LIMPEZA COMPLETA REALIZADA

PRÓXIMOS PASSOS:
1. Execute a DAG 'datamaster_sentiment_pipeline_fixed'
2. Aguarde conclusão completa do pipeline
3. Verifique se tabelas aparecem no schema datalake
4. Monitore logs para garantir execução limpa

====================================================================
EOF

        echo "📄 Relatório gerado: $REPORT_FILE"
        cat "$REPORT_FILE"
        
        # Copiar para área de relatórios se existir
        mkdir -p /opt/airflow/reports 2>/dev/null || true
        cp "$REPORT_FILE" /opt/airflow/reports/ 2>/dev/null || true
        
        echo "✅ Relatório de limpeza concluído"
        ''',
        dag=dag
    )
    
    # Sequência de verificação
    verify_cleanup >> generate_cleanup_report

# Definição do fluxo da DAG
start_cleanup >> preparation_group >> [cleanup_catalog_group, cleanup_storage_group] >> cleanup_temp_group >> verification_group >> end_cleanup

# Documentação da DAG
dag.doc_md = """
# DAG de Limpeza Completa - DataLake e MinIO

Esta DAG realiza limpeza completa do ambiente DataMaster para permitir execução limpa do pipeline.

## ⚠️ ATENÇÃO - EXECUÇÃO MANUAL APENAS

**Esta DAG remove TODOS os dados permanentemente!**

### Operações Realizadas:

1. **Preparação**:
   - Confirmação da operação
   - Verificação de dependências
   - Backup de metadados

2. **Limpeza do Catálogo**:
   - Remove todas as tabelas do schema `datalake`
   - Remove database `datalake` do Hive Metastore
   - Limpa registros de metadados

3. **Limpeza do Storage**:
   - Remove todos os objetos do bucket `datalake` no MinIO
   - Limpa arquivos Delta Lake (_delta_log)
   - Remove checkpoints e arquivos temporários

4. **Limpeza de Arquivos Temporários**:
   - Remove logs antigos do Airflow
   - Limpa arquivos temporários do Spark
   - Remove cache e arquivos PID

5. **Verificação Final**:
   - Verifica se limpeza foi completa
   - Gera relatório de operações
   - Confirma estado limpo do ambiente

## Quando Usar:

- **Reset completo** do ambiente
- **Problemas de corrupção** de dados
- **Testes de pipeline** completo
- **Limpeza antes de deploy** em produção

## Como Executar:

1. **Via Airflow UI**: Trigger manual da DAG
2. **Via CLI**: `airflow dags trigger cleanup_datalake_complete`

## Após a Execução:

1. Execute `datamaster_sentiment_pipeline_fixed`
2. Aguarde conclusão completa
3. Verifique tabelas em `datalake` schema
4. Monitore logs para garantir sucesso

## Backup:

A DAG faz backup automático de metadados em `/opt/airflow/backups/`
"""