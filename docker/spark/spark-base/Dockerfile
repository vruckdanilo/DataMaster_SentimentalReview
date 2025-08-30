# Base image for Spark with OpenJDK 8
FROM openjdk:8-jdk-slim

# Define the Spark version and Hadoop version
ARG SPARK_VERSION=3.4.0
ARG HADOOP_VERSION=3

# Set environment variables for Spark
ENV SPARK_HOME=/opt/spark
ENV PATH=$SPARK_HOME/bin:$SPARK_HOME/sbin:$PATH

# Install necessary packages including Python 3 and pip
RUN apt-get update && \
    apt-get install -y curl bash tar python3 python3-distutils && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3 && \
    rm -rf /var/lib/apt/lists/*

# Download and install Spark
RUN curl -o spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz \
    https://archive.apache.org/dist/spark/spark-${SPARK_VERSION}/spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz && \
    tar -xzf spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz && \
    mv spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION} $SPARK_HOME && \
    rm spark-${SPARK_VERSION}-bin-hadoop${HADOOP_VERSION}.tgz

# Download necessary JARs for AWS S3, Delta Lake, and MySQL
RUN curl -O https://repo1.maven.org/maven2/io/delta/delta-core_2.12/2.4.0/delta-core_2.12-2.4.0.jar \
    && curl -O https://repo1.maven.org/maven2/io/delta/delta-storage/2.4.0/delta-storage-2.4.0.jar \
    && curl -O https://repo1.maven.org/maven2/software/amazon/awssdk/s3/2.18.41/s3-2.18.41.jar \
    && curl -O https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk/1.12.367/aws-java-sdk-1.12.367.jar \
    && curl -O https://repo1.maven.org/maven2/mysql/mysql-connector-java/8.0.19/mysql-connector-java-8.0.19.jar \
    && curl -O https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar \
    && curl -O https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.367/aws-java-sdk-bundle-1.12.367.jar \
    && mv *.jar $SPARK_HOME/jars/

# Copy configuration files for Spark, Hive, and log4j
COPY hive-site.xml $SPARK_HOME/conf/hive-site.xml
COPY log4j.properties $SPARK_HOME/conf/log4j.properties
COPY spark-defaults.conf $SPARK_HOME/conf/spark-defaults.conf

# Install Python dependencies
COPY requirements.txt . 
RUN python3 -m pip install --no-cache-dir -r requirements.txt
RUN pip install minio

# Expose ports for Spark UI and communication
EXPOSE 8080 7077 6066 8081 8082

# Set the working directory
WORKDIR $SPARK_HOME

# Default command
CMD ["bash"]
