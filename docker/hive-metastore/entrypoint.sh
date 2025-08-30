#!/bin/bash

# Set environment variables for Hadoop and Java paths
export HADOOP_HOME=/opt/hadoop-3.2.1
export HIVE_HOME=/opt/metastore
export HADOOP_CLASSPATH=$($HADOOP_HOME/bin/hadoop classpath)
# Set environment variables
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH

# Make sure MariaDB is ready
MAX_TRIES=8
CURRENT_TRY=1
SLEEP_BETWEEN_TRY=4

until nc -z mysql 3306 || [ "$CURRENT_TRY" -gt "$MAX_TRIES" ]; do
    echo "Waiting for MySQL server to be ready... ($CURRENT_TRY/$MAX_TRIES)"
    sleep "$SLEEP_BETWEEN_TRY"
    CURRENT_TRY=$((CURRENT_TRY + 1))
done

if [ "$CURRENT_TRY" -gt "$MAX_TRIES" ]; then
  echo "WARNING: Timeout when waiting for MySQL."
else
  echo "MySQL server is ready!"
fi

# Continue with the rest of the entrypoint logic
# For example, initialize Hive Metastore schema if needed
$HIVE_HOME/bin/schematool -initSchema -dbType mysql -ifNotExists

# Start the Hive Metastore service
$HIVE_HOME/bin/start-metastore
