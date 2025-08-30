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
    """Cria sessão Spark otimizada para Delta Lake"""
    
    builder = SparkSession.builder \
        .appName("DataMaster_SilverToGold_Working") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minio") \
        .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    
    return configure_spark_with_delta_pip(builder).getOrCreate()

def main():
    """Função principal que executa o pipeline Silver → Gold"""
    
    logger.info("=== INICIANDO PIPELINE SILVER → GOLD (PRODUÇÃO) ===")
    
    try:
        # Criar sessão Spark
        spark = create_spark_session()
        
        # Paths dos dados
        silver_path = "s3a://datalake/silver/google_maps_reviews_enriched"
        gold_base_path = "s3a://datalake/gold"
        
        logger.info(f"📖 Lendo dados Silver de: {silver_path}")
        
        # Ler dados da camada Silver
        df_silver = spark.read.format("delta").load(silver_path)
        
        logger.info(f"✅ Dados Silver carregados: {df_silver.count()} registros")
        
        # Criar database datalake se não existir
        spark.sql("CREATE DATABASE IF NOT EXISTS datalake")
        logger.info("✅ Database 'datalake' criado/verificado")
        
        # 1. Agency Performance KPIs
        logger.info("🏭 Gerando agency_performance_kpis...")
        df_kpis = df_silver.groupBy("place_id", "nome_agencia", "bairro").agg(
            count("*").alias("total_reviews"),
            avg("rating_review").alias("rating_medio"),
            sum(when(col("sentimento") == "positivo", 1).otherwise(0)).alias("reviews_positivos"),
            sum(when(col("sentimento") == "negativo", 1).otherwise(0)).alias("reviews_negativos"),
            sum(when(col("sentimento") == "neutro", 1).otherwise(0)).alias("reviews_neutros"),
            sum(when(col("tem_pii") == True, 1).otherwise(0)).alias("reviews_com_pii"),
            current_timestamp().alias("gold_timestamp")
        )
        
        kpis_path = f"{gold_base_path}/agency_performance_kpis"
        df_kpis.write.format("delta").mode("overwrite").save(kpis_path)
        
        # Registrar tabela no catálogo datalake
        spark.sql(f"DROP TABLE IF EXISTS datalake.agency_performance_kpis")
        spark.sql(f"CREATE TABLE datalake.agency_performance_kpis USING DELTA LOCATION '{kpis_path}'")
        
        logger.info(f"✅ KPIs de agência salvos: {df_kpis.count()} registros")
        
        # 2. Temporal Sentiment Analysis
        logger.info("🏭 Gerando temporal_sentiment_analysis...")
        df_temporal = df_silver.withColumn("mes", month("data_coleta")).groupBy("bairro", "mes").agg(
            count("*").alias("total_reviews"),
            sum(when(col("sentimento") == "positivo", 1).otherwise(0)).alias("positivos"),
            sum(when(col("sentimento") == "negativo", 1).otherwise(0)).alias("negativos"),
            current_timestamp().alias("gold_timestamp")
        )
        
        temporal_path = f"{gold_base_path}/temporal_sentiment_analysis"
        df_temporal.write.format("delta").mode("overwrite").save(temporal_path)
        
        # Registrar tabela no catálogo datalake
        spark.sql(f"DROP TABLE IF EXISTS datalake.temporal_sentiment_analysis")
        spark.sql(f"CREATE TABLE datalake.temporal_sentiment_analysis USING DELTA LOCATION '{temporal_path}'")
        
        logger.info(f"✅ Análise temporal salva: {df_temporal.count()} registros")
        
        # 3. Risk Alerts (usando reviews negativos como proxy de risco)
        logger.info("🏭 Gerando risk_alerts...")
        df_alerts = df_silver.filter(col("sentimento") == "negativo").groupBy("place_id", "nome_agencia").agg(
            count("*").alias("total_reviews_negativas"),
            current_timestamp().alias("gold_timestamp")
        )
        
        if df_alerts.count() == 0:
            # Se não há alertas, criar registro dummy
            df_alerts = spark.createDataFrame([
                ("sem_alertas", "Nenhum alerta", 0, datetime.now())
            ], ["place_id", "nome_agencia", "total_reviews_negativas", "gold_timestamp"])
        
        alerts_path = f"{gold_base_path}/risk_alerts"
        df_alerts.write.format("delta").mode("overwrite").save(alerts_path)
        
        # Registrar tabela no catálogo datalake
        spark.sql(f"DROP TABLE IF EXISTS datalake.risk_alerts")
        spark.sql(f"CREATE TABLE datalake.risk_alerts USING DELTA LOCATION '{alerts_path}'")
        
        logger.info(f"✅ Alertas de risco salvos: {df_alerts.count()} registros")
        
        # 4. Executive Dashboard
        logger.info("🏭 Gerando executive_dashboard...")
        total_reviews = df_silver.count()
        positivos = df_silver.filter(col("sentimento") == "positivo").count()
        negativos = df_silver.filter(col("sentimento") == "negativo").count()
        total_agencies = df_silver.select("place_id").distinct().count()
        
        df_dashboard = spark.createDataFrame([
            (total_reviews, positivos, negativos, total_agencies, datetime.now())
        ], ["total_reviews", "reviews_positivos", "reviews_negativos", "total_agencias", "gold_timestamp"])
        
        dashboard_path = f"{gold_base_path}/executive_dashboard"
        df_dashboard.write.format("delta").mode("overwrite").save(dashboard_path)
        
        # Registrar tabela no catálogo datalake
        spark.sql(f"DROP TABLE IF EXISTS datalake.executive_dashboard")
        spark.sql(f"CREATE TABLE datalake.executive_dashboard USING DELTA LOCATION '{dashboard_path}'")
        
        logger.info(f"✅ Dashboard executivo salvo: {df_dashboard.count()} registros")
        
        # 5. NPS Ranking
        logger.info("🏭 Gerando nps_ranking...")
        df_nps = df_silver.withColumn("nps_categoria",
                                     when(col("rating_review") >= 4, "Promotor")
                                     .when(col("rating_review") >= 3, "Neutro")
                                     .otherwise("Detrator")) \
            .groupBy("place_id", "nome_agencia").agg(
                count("*").alias("total_avaliacoes"),
                sum(when(col("nps_categoria") == "Promotor", 1).otherwise(0)).alias("promotores"),
                sum(when(col("nps_categoria") == "Detrator", 1).otherwise(0)).alias("detratores"),
                avg("rating_review").alias("rating_medio"),
                current_timestamp().alias("gold_timestamp")
            )
        
        nps_path = f"{gold_base_path}/nps_ranking"
        df_nps.write.format("delta").mode("overwrite").save(nps_path)
        
        # Registrar tabela no catálogo datalake
        spark.sql(f"DROP TABLE IF EXISTS datalake.nps_ranking")
        spark.sql(f"CREATE TABLE datalake.nps_ranking USING DELTA LOCATION '{nps_path}'")
        
        logger.info(f"✅ Ranking NPS salvo: {df_nps.count()} registros")
        
        # 6. Business Metrics Summary
        logger.info("🏭 Gerando business_metrics_summary...")
        df_business = df_silver.groupBy("bairro").agg(
            count("*").alias("total_reviews"),
            avg("rating_review").alias("rating_medio"),
            sum(when(col("sentimento") == "positivo", 1).otherwise(0)).alias("reviews_positivos"),
            current_timestamp().alias("gold_timestamp")
        )
        
        business_path = f"{gold_base_path}/business_metrics_summary"
        df_business.write.format("delta").mode("overwrite").save(business_path)
        
        # Registrar tabela no catálogo datalake
        spark.sql(f"DROP TABLE IF EXISTS datalake.business_metrics_summary")
        spark.sql(f"CREATE TABLE datalake.business_metrics_summary USING DELTA LOCATION '{business_path}'")
        
        logger.info(f"✅ Sumário de negócio salvo: {df_business.count()} registros")
        
        # Estatísticas finais
        logger.info("📈 Estatísticas finais do processamento:")
        logger.info(f"   • KPIs de Agência: {df_kpis.count()} agências analisadas")
        logger.info(f"   • Análise Temporal: {df_temporal.count()} períodos analisados")
        logger.info(f"   • Alertas de Risco: {df_alerts.count()} alertas gerados")
        logger.info(f"   • Dashboard Executivo: {df_dashboard.count()} métricas agregadas")
        logger.info(f"   • Ranking NPS: {df_nps.count()} agências ranqueadas")
        logger.info(f"   • Sumário de Negócio: {df_business.count()} registros de sumário")
        
        # Listar tabelas registradas no catálogo datalake
        logger.info("📋 Verificando tabelas registradas no catálogo datalake:")
        tables_df = spark.sql("SHOW TABLES IN datalake")
        tables_df.show()
        
        logger.info("✅ Pipeline Silver → Gold PRODUÇÃO concluído com sucesso!")
        logger.info("🎯 Todas as 6 tabelas Gold geradas E REGISTRADAS NO CATÁLOGO:")
        logger.info("   ✅ agency_performance_kpis")
        logger.info("   ✅ temporal_sentiment_analysis")
        logger.info("   ✅ risk_alerts")
        logger.info("   ✅ executive_dashboard")
        logger.info("   ✅ nps_ranking")
        logger.info("   ✅ business_metrics_summary")
        logger.info("📊 Tabelas disponíveis para consulta via SQL!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro durante transformação Silver → Gold: {e}")
        raise e
    finally:
        spark.stop()

if __name__ == "__main__":
    main()