#!/usr/bin/env python3


from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from delta import configure_spark_with_delta_pip
import logging
import re
from datetime import datetime

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Cria sessão Spark otimizada para Delta Lake com NLP"""
    
    logger.info("Criando sessão Spark...")
    
    builder = SparkSession.builder \
        .appName("DataMaster_BronzeToSilver_Fixed") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.warehouse.dir", "s3a://datalake/warehouse") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    
    return configure_spark_with_delta_pip(builder).getOrCreate()

def sentiment_analysis_ptbr_udf():
    """UDF para análise de sentimento em português brasileiro"""
    
    # Dicionários de palavras para análise de sentimento
    palavras_positivas = {
        'excelente', 'ótimo', 'bom', 'maravilhoso', 'fantástico', 'perfeito', 'incrível',
        'satisfeito', 'feliz', 'contente', 'agradável', 'recomendo', 'aprovado', 'amei',
        'gostei', 'adorei', 'parabéns', 'eficiente', 'rápido', 'prático', 'fácil',
        'atencioso', 'educado', 'prestativo', 'cordial', 'profissional', 'competente',
        'organizado', 'limpo', 'confortável', 'seguro', 'confiável', 'qualidade'
    }
    
    palavras_negativas = {
        'péssimo', 'horrível', 'ruim', 'terrível', 'desastroso', 'lamentável', 'decepcionante',
        'insatisfeito', 'irritado', 'chateado', 'frustrado', 'raiva', 'ódio', 'detesto',
        'não recomendo', 'reprovado', 'odiei', 'problemático', 'demorado', 'lento', 'difícil',
        'mal educado', 'grosso', 'incompetente', 'desorganizado', 'sujo', 'desconfortável',
        'inseguro', 'duvidoso', 'baixa qualidade', 'fraude', 'golpe', 'enganação'
    }
    
    def analyze_sentiment(text):
        if text is None or text.strip() == "":
            return "neutro"
        
        text_lower = text.lower()
        
        # Conta palavras positivas e negativas
        positivas_count = len([palavra for palavra in palavras_positivas if palavra in text_lower])
        negativas_count = len([palavra for palavra in palavras_negativas if palavra in text_lower])
        
        # Análise baseada em contagem
        if positivas_count > negativas_count:
            return "positivo"
        elif negativas_count > positivas_count:
            return "negativo"
        else:
            return "neutro"
    
    return udf(analyze_sentiment, StringType())

def detect_pii_udf():
    """UDF para detecção de PII (dados pessoais)"""
    
    def detect_pii(text):
        if text is None or text.strip() == "":
            return (False, [], text)
        
        pii_detected = []
        anonymized_text = text
        
        # CPF pattern
        cpf_pattern = r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'
        if re.search(cpf_pattern, text):
            pii_detected.append("cpf")
            anonymized_text = re.sub(cpf_pattern, '[CPF_ANONIMIZADO]', anonymized_text)
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, text):
            pii_detected.append("email")
            anonymized_text = re.sub(email_pattern, '[EMAIL_ANONIMIZADO]', anonymized_text)
        
        # Telefone pattern
        phone_pattern = r'(\(?\d{2}\)?[\s\-]?\d{4,5}[\s\-]?\d{4})'
        if re.search(phone_pattern, text):
            pii_detected.append("telefone")
            anonymized_text = re.sub(phone_pattern, '[TELEFONE_ANONIMIZADO]', anonymized_text)
        
        has_pii = len(pii_detected) > 0
        
        return (has_pii, pii_detected, anonymized_text)
    
    return udf(detect_pii, StructType([
        StructField("tem_pii", BooleanType(), True),
        StructField("tipos_pii", ArrayType(StringType()), True),
        StructField("texto_anonimizado", StringType(), True)
    ]))

def transform_bronze_to_silver(spark, bronze_path, silver_path):
    """Transforma dados da camada Bronze para Silver"""
    
    logger.info(f"=== TRANSFORMAÇÃO BRONZE → SILVER ===")
    logger.info(f"Bronze: {bronze_path}")
    logger.info(f"Silver: {silver_path}")
    
    try:
        # 1. Carrega dados Bronze
        logger.info("1. Carregando dados Bronze...")
        df_bronze = spark.read.format("delta").load(bronze_path)
        
        bronze_count = df_bronze.count()
        logger.info(f"   ✅ Bronze: {bronze_count} registros")
        
        # Mostra estrutura dos dados
        logger.info("   Schema do Bronze:")
        df_bronze.printSchema()
        
        # 2. Filtra registros com review text
        logger.info("2. Filtrando registros com review text...")
        df_with_reviews = df_bronze.filter(
            (col("review_text").isNotNull()) & 
            (trim(col("review_text")) != "")
        )
        
        valid_count = df_with_reviews.count()
        logger.info(f"   ✅ Com reviews válidos: {valid_count} registros")
        
        if valid_count == 0:
            logger.warning("⚠️ Nenhum registro com review_text válido encontrado!")
            return False
        
        # 3. Aplica análise de sentimento
        logger.info("3. Aplicando análise de sentimento...")
        sentiment_udf = sentiment_analysis_ptbr_udf()
        
        df_with_sentiment = df_with_reviews.withColumn(
            "sentimento_analise", 
            sentiment_udf(col("review_text"))
        )
        
        # 4. Aplica detecção de PII
        logger.info("4. Aplicando detecção de PII...")
        pii_udf = detect_pii_udf()
        
        df_with_pii = df_with_sentiment.withColumn(
            "pii_analysis", 
            pii_udf(col("review_text"))
        )
        
        # 5. Estrutura dados para Silver
        logger.info("5. Estruturando dados para Silver...")
        df_silver = df_with_pii.select(
            col("place_id"),
            col("agencia_name").alias("nome_agencia"),
            col("endereco_completo"),
            col("latitude"),
            col("longitude"),
            col("agencia_rating").alias("rating_agencia"),
            col("total_avaliacoes"),
            col("bairro_pesquisado").alias("bairro"),
            col("data_coleta"),
            col("author_name").alias("review_autor"),
            col("review_rating").alias("rating_review"),
            col("review_text").alias("texto_review"),
            col("review_time").alias("data_review"),
            col("sentimento_analise").alias("sentimento"),
            col("pii_analysis.tem_pii").alias("tem_pii"),
            col("pii_analysis.tipos_pii").alias("tipos_pii_detectados"),
            col("pii_analysis.texto_anonimizado").alias("texto_anonimizado"),
            current_timestamp().alias("silver_processing_timestamp"),
            year(current_date()).alias("partition_year"),
            month(current_date()).alias("partition_month"),
            dayofmonth(current_date()).alias("partition_day")
        ).withColumn(
            "data_quality_score", 
            when((col("texto_review").isNotNull()) & 
                 (length(col("texto_review")) > 10), 1.0)
            .otherwise(0.5)
        )
        
        final_count = df_silver.count()
        logger.info(f"   ✅ Dados estruturados: {final_count} registros")
        
        # 6. Mostra amostra
        logger.info("6. Amostra dos dados Silver:")
        df_silver.select("nome_agencia", "bairro", "rating_review", "sentimento", "tem_pii").show(5, truncate=False)
        
        # 7. Salva na Silver
        logger.info("7. Salvando dados Silver...")
        df_silver.write \
            .format("delta") \
            .mode("overwrite") \
            .partitionBy("partition_year", "partition_month", "bairro") \
            .save(silver_path)
        
        logger.info("   ✅ Dados salvos na camada Silver!")
        
        # 8. Estatísticas de sentimento
        logger.info("8. Estatísticas de sentimento:")
        sentiment_stats = df_silver.groupBy("sentimento").count().collect()
        for stat in sentiment_stats:
            logger.info(f"   {stat['sentimento']}: {stat['count']} reviews")
        
        # 9. Estatísticas de PII
        logger.info("9. Estatísticas de PII:")
        pii_stats = df_silver.groupBy("tem_pii").count().collect()
        for stat in pii_stats:
            logger.info(f"   PII detectado={stat['tem_pii']}: {stat['count']} reviews")
        
        logger.info("✅ PIPELINE BRONZE → SILVER CONCLUÍDO COM SUCESSO!")
        return True
        
    except Exception as e:
        logger.error(f"Erro durante transformação Bronze → Silver: {str(e)}")
        raise e

def main():
    """Função principal do pipeline de transformação"""
    
    logger.info("=== INICIANDO PIPELINE BRONZE → SILVER (FIXED) ===")
    
    # Cria sessão Spark
    spark = create_spark_session()
    
    try:
        import sys
        
        if len(sys.argv) > 1:
            bronze_path = sys.argv[1]
            silver_path = sys.argv[2] if len(sys.argv) > 2 else "s3a://datalake/silver/google_maps_reviews_enriched"
        else:
            # Caminhos padrão
            bronze_path = "s3a://datalake/bronze/google_maps_reviews"
            silver_path = "s3a://datalake/silver/google_maps_reviews_enriched"
        
        # Executa transformação
        success = transform_bronze_to_silver(spark, bronze_path, silver_path)
        
        if success:
            logger.info("=== PIPELINE BRONZE → SILVER CONCLUÍDO COM SUCESSO ===")
        else:
            logger.error("=== PIPELINE BRONZE → SILVER FALHOU ===")
            
        return success
        
    except Exception as e:
        logger.error(f"Erro na execução principal: {str(e)}")
        return False
        
    finally:
        spark.stop()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)