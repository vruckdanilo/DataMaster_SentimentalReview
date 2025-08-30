#!/usr/bin/env python3


from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from delta import configure_spark_with_delta_pip
import logging
from datetime import datetime

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Cria sessão Spark otimizada para Delta Lake com configurações MinIO"""
    
    builder = SparkSession.builder \
        .appName("DataMaster_LandingToBronze_Fixed") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.warehouse.dir", "s3a://datalake/warehouse") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    
    return configure_spark_with_delta_pip(builder).getOrCreate()

def expand_reviews_fixed(df_agencias, spark):
    """Expande array de reviews em registros individuais - VERSÃO CORRIGIDA"""
    
    logger.info("Expandindo reviews individuais...")
    
    # Mostrar colunas disponíveis
    columns = df_agencias.columns
    logger.info(f"Colunas disponíveis: {columns}")
    
    # Verificar se reviews existem e não são nulos
    df_with_reviews_check = df_agencias.filter(
        col("reviews").isNotNull() & 
        (size(col("reviews")) > 0)
    )
    
    count_with_reviews = df_with_reviews_check.count()
    logger.info(f"Registros com reviews: {count_with_reviews}")
    
    if count_with_reviews == 0:
        logger.warning("⚠️ Nenhum registro com reviews encontrado!")
        # Criar DataFrame vazio com schema esperado
        empty_schema = StructType([
            StructField("place_id", StringType(), True),
            StructField("agencia_name", StringType(), True),
            StructField("endereco_completo", StringType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("agencia_rating", DoubleType(), True),
            StructField("total_avaliacoes", IntegerType(), True),
            StructField("bairro_pesquisado", StringType(), True),
            StructField("data_coleta", StringType(), True),
            StructField("data_coleta_timestamp", TimestampType(), True),
            StructField("bronze_ingestion_timestamp", TimestampType(), True),
            StructField("bronze_ingestion_date", DateType(), True),
            StructField("data_quality_score", DoubleType(), True),
            StructField("source_system", StringType(), True),
            StructField("author_name", StringType(), True),
            StructField("review_rating", IntegerType(), True),
            StructField("review_text", StringType(), True),
            StructField("review_time", LongType(), True),
            StructField("bronze_review_id", StringType(), True)
        ])
        return spark.createDataFrame([], empty_schema)
    
    # Criar explode dos reviews
    df_with_reviews = df_with_reviews_check.withColumn("review", explode(col("reviews")))
    
    # Selecionar colunas finais com tratamento de nulos
    df_final = df_with_reviews.select(
        col("place_id"),
        col("name").alias("agencia_name"),
        col("formatted_address").alias("endereco_completo"),
        col("latitude"),
        col("longitude"),
        col("rating").alias("agencia_rating"),
        col("total_avaliacoes"),
        col("bairro_pesquisado"),
        col("data_coleta"),
        col("data_coleta_timestamp"),
        col("bronze_ingestion_timestamp"),
        col("bronze_ingestion_date"),
        col("data_quality_score"),
        col("source_system"),
        coalesce(col("review.author_name"), lit("Anônimo")).alias("author_name"),
        coalesce(col("review.rating"), lit(0)).alias("review_rating"),
        coalesce(col("review.text"), lit("")).alias("review_text"),
        coalesce(col("review.time"), lit(0)).alias("review_time")
    )
    
    # Adiciona ID único para cada review
    df_final = df_final.withColumn("bronze_review_id", 
                                 concat(col("place_id"), lit("_"), 
                                       hash(concat(col("author_name"), col("review_text"), col("review_time"))).cast("string")))
    
    final_count = df_final.count()
    logger.info(f"Reviews expandidos: {final_count} registros")
    
    return df_final

def ingest_landing_to_bronze(spark, landing_path, bronze_path):
    """Ingere dados da landing para Bronze com processamento completo"""
    
    logger.info(f"Iniciando ingestão Landing → Bronze")
    logger.info(f"Landing Path: {landing_path}")
    logger.info(f"Bronze Path: {bronze_path}")
    
    try:
        # Lê dados da landing - busca recursiva automática
        logger.info("Buscando arquivos recursivamente na landing zone...")
        
        try:
            # Usa recursiveFileLookup para encontrar qualquer arquivo JSON
            df_raw = spark.read \
                .option("recursiveFileLookup", "true") \
                .option("multiline", "true") \
                .json(landing_path)
            
            logger.info(f"✅ Dados encontrados na landing zone")
        except Exception as e:
            logger.error(f"❌ Erro ao ler landing zone: {e}")
            df_raw = None
        
        if df_raw is None:
            raise Exception("Nenhum arquivo JSON encontrado em nenhum padrão!")
        
        logger.info(f"Dados brutos carregados: {df_raw.count()} registros")
        
        # Verificar estrutura dos dados
        columns = df_raw.columns
        logger.info(f"Colunas disponíveis: {columns}")
        df_raw.printSchema()
        df_raw.show(2, truncate=False)
        
        # Adaptação para diferentes estruturas de dados
        if "reviews" in columns:
            # Estrutura simples: [{"place_id": "...", "reviews": [...]}]
            logger.info("📊 Detectada estrutura simples de reviews")
            df_agencias = df_raw.select(
                lit(current_date().cast("string")).alias("data_coleta"),
                coalesce(col("bairro"), lit("centro")).alias("bairro_pesquisado"),
                col("place_id"),
                coalesce(col("name"), lit("Local Desconhecido")).alias("name"),
                coalesce(col("formatted_address"), lit("Endereço não informado")).alias("formatted_address"),
                lit(0.0).alias("latitude"),
                lit(0.0).alias("longitude"),
                coalesce(col("rating"), lit(0.0)).alias("rating"),
                lit(0).alias("total_avaliacoes"),
                col("reviews")
            )
        else:
            # Estrutura mais complexa com metadata
            logger.info("📊 Detectada estrutura complexa com metadata")
            df_agencias_exploded = df_raw.select(
                col("execution_metadata.execution_date").alias("data_coleta"),
                col("execution_metadata.bairro").alias("bairro_pesquisado"),
                explode(col("raw_data.agencias")).alias("agencia")
            )
            
            # Primeiro explodir agências, depois reviews
            df_agencias_with_reviews = df_agencias_exploded.select(
                col("data_coleta"),
                col("bairro_pesquisado"),
                col("agencia.place_id").alias("place_id"),
                col("agencia.name").alias("name"),
                col("agencia.formatted_address").alias("formatted_address"),
                coalesce(col("agencia.geometry.location.lat"), lit(0.0)).alias("latitude"),
                coalesce(col("agencia.geometry.location.lng"), lit(0.0)).alias("longitude"),
                coalesce(col("agencia.rating"), lit(0.0)).alias("rating"),
                coalesce(col("agencia.user_ratings_total"), lit(0)).alias("total_avaliacoes"),
                coalesce(col("agencia.reviews"), array().cast("array<struct<author_name:string,rating:int,text:string,time:bigint>>")).alias("reviews")
            )
            
            df_agencias = df_agencias_with_reviews
        
        logger.info(f"Dados das agências extraídos: {df_agencias.count()} registros")
        
        # Adicionar colunas de controle
        df_agencias = df_agencias \
            .withColumn("bronze_ingestion_timestamp", current_timestamp()) \
            .withColumn("bronze_ingestion_date", current_date()) \
            .withColumn("data_quality_score", 
                       when((col("place_id").isNotNull()) & 
                            (col("name").isNotNull()) & 
                            (col("bairro_pesquisado").isNotNull()), 1.0)
                       .otherwise(0.5)) \
            .withColumn("source_system", lit("google_maps_api")) \
            .withColumn("data_coleta_timestamp", 
                       to_timestamp(col("data_coleta"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"))
        
        # Filtrar apenas registros com place_id válido
        df_agencias = df_agencias.filter(col("place_id").isNotNull())
        
        # Expandir reviews
        df_final = expand_reviews_fixed(df_agencias, spark)
        
        # Particionar dados
        df_partitioned = df_final.withColumn("partition_year", year(col("bronze_ingestion_date"))) \
                                .withColumn("partition_month", month(col("bronze_ingestion_date"))) \
                                .withColumn("partition_day", dayofmonth(col("bronze_ingestion_date")))
        
        # Salvar na camada Bronze com overwrite para evitar conflitos de schema
        df_partitioned.write \
            .format("delta") \
            .mode("overwrite") \
            .partitionBy("partition_year", "partition_month", "partition_day", "bairro_pesquisado") \
            .option("mergeSchema", "true") \
            .save(bronze_path)
        
        logger.info(f"Dados salvos com sucesso na camada Bronze: {bronze_path}")
        
        # Estatísticas finais
        final_count = df_partitioned.count()
        unique_places = df_partitioned.select("place_id").distinct().count()
        unique_bairros = df_partitioned.select("bairro_pesquisado").distinct().count()
        
        logger.info(f"ESTATÍSTICAS FINAIS:")
        logger.info(f"- Total reviews processados: {final_count}")
        logger.info(f"- Agências únicas: {unique_places}")
        logger.info(f"- Bairros únicos: {unique_bairros}")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro durante ingestão Landing → Bronze: {str(e)}")
        raise e

def main():
    """Função principal do pipeline de ingestão"""
    
    logger.info("=== INICIANDO PIPELINE LANDING → BRONZE (FIXED) ===")
    
    # Cria sessão Spark
    spark = create_spark_session()
    
    try:
        import sys
        
        if len(sys.argv) > 1:
            landing_path = sys.argv[1]
            bronze_path = sys.argv[2] if len(sys.argv) > 2 else "s3a://datalake/bronze/google_maps_reviews"
        else:
            # Usar dados do MinIO
            landing_path = "s3a://datalake/landing/google_maps/*/*/*/*/*.json"
            bronze_path = "s3a://datalake/bronze/google_maps_reviews"
        
        # Executa ingestão
        success = ingest_landing_to_bronze(spark, landing_path, bronze_path)
        
        if success:
            logger.info("=== PIPELINE LANDING → BRONZE CONCLUÍDO COM SUCESSO ===")
        else:
            logger.error("=== PIPELINE LANDING → BRONZE FALHOU ===")
            
        return success
        
    except Exception as e:
        logger.error(f"Erro na execução principal: {str(e)}")
        return False
        
    finally:
        spark.stop()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)