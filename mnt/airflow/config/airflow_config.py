

# Configurações de logging
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'airflow': {
            'format': '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'airflow',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'json',
            'filename': '/opt/airflow/logs/datamaster.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'loggers': {
        'datamaster': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

# Configurações de conexões padrão
DEFAULT_CONNECTIONS = {
    'minio_default': {
        'conn_type': 's3',
        'host': 'minio',
        'port': 9000,
        'login': 'minio',
        'password': 'minio123',
        'extra': '{"aws_access_key_id": "minio", "aws_secret_access_key": "minio123", "endpoint_url": "http://minio:9000"}'
    },
    'kafka_default': {
        'conn_type': 'kafka',
        'host': 'kafka',
        'port': 9092,
        'extra': '{"bootstrap_servers": "kafka:9092"}'
    },
    'spark_default': {
        'conn_type': 'spark',
        'host': 'spark-master',
        'port': 7077,
        'extra': '{"master": "spark://spark-master:7077"}'
    }
}

# Variáveis padrão do Airflow
DEFAULT_VARIABLES = {
    'datamaster_env': 'development',
    'datamaster_version': '1.0.0',
    'google_maps_rate_limit': '10',
    'spark_executor_memory': '2g',
    'spark_executor_cores': '2',
    'minio_bucket_landing': 'landing',
    'minio_bucket_bronze': 'bronze',
    'minio_bucket_silver': 'silver',
    'minio_bucket_gold': 'gold'
}

# Configurações de pools
DEFAULT_POOLS = {
    'google_maps_pool': {
        'slots': 2,
        'description': 'Pool para limitação de chamadas Google Maps API'
    },
    'spark_pool': {
        'slots': 1,
        'description': 'Pool para jobs PySpark'
    }
}

# Tags padrão para DAGs
DEFAULT_TAGS = [
    'datamaster',
    'santander',
    'sentimento',
    'data-lakehouse'
]

