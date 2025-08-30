FROM apache/airflow:2.7.1

# Instalar apenas dependências essenciais que faltam
USER airflow
RUN pip install --no-cache-dir kafka-python minio apache-airflow-providers-apache-spark==4.1.3 requests

# Instalar curl e criar diretório scripts
USER root
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt/airflow/scripts && chown -R airflow:root /opt/airflow/scripts

# Voltar para usuário airflow  
USER airflow
