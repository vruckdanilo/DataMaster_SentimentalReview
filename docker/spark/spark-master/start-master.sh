#!/bin/bash

# Start Spark Master
echo "Starting Spark Master..."
$SPARK_HOME/bin/spark-class org.apache.spark.deploy.master.Master \
    --host spark-master \
    --port $SPARK_MASTER_PORT \
    --webui-port $SPARK_MASTER_UI_PORT
