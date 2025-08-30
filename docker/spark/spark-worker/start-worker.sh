#!/bin/bash

# Start Spark Worker
echo "Starting Spark Worker..."
$SPARK_HOME/bin/spark-class org.apache.spark.deploy.worker.Worker \
    --webui-port $SPARK_WORKER_UI_PORT \
    spark://spark-master:7077
