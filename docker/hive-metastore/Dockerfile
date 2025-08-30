# Use Ubuntu as the base image
FROM ubuntu:20.04

WORKDIR /opt

# Set environment variables for versions
ENV HADOOP_VERSION=3.2.1
ENV METASTORE_VERSION=3.1.2

# Set paths for Hadoop and Hive
ENV HADOOP_HOME=/opt/hadoop-${HADOOP_VERSION}
ENV HIVE_HOME=/opt/metastore
ENV PATH=$PATH:$HIVE_HOME/bin:$HADOOP_HOME/bin

# Install necessary utilities and Java 8
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk curl tar wget netcat && \
    rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME to the correct path for Ubuntu
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

# Download and extract Hive Standalone Metastore, Hadoop, and MySQL Connector
RUN wget https://repo1.maven.org/maven2/org/apache/hive/hive-standalone-metastore/${METASTORE_VERSION}/hive-standalone-metastore-${METASTORE_VERSION}-bin.tar.gz && \
    tar -xvf hive-standalone-metastore-${METASTORE_VERSION}-bin.tar.gz && \
    mv apache-hive-metastore-${METASTORE_VERSION}-bin metastore && \
    wget https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz && \
    tar -xvf hadoop-${HADOOP_VERSION}.tar.gz && \
    wget https://dev.mysql.com/get/Downloads/Connector-J/mysql-connector-java-8.0.19.tar.gz && \
    tar -xvf mysql-connector-java-8.0.19.tar.gz && \
    cp mysql-connector-java-8.0.19/mysql-connector-java-8.0.19.jar ${HIVE_HOME}/lib/ && \
    rm -rf mysql-connector-java-8.0.19 hive-standalone-metastore-${METASTORE_VERSION}-bin.tar.gz hadoop-${HADOOP_VERSION}.tar.gz mysql-connector-java-8.0.19.tar.gz

# Replace conflicting libraries and add missing libraries
RUN rm -f ${HIVE_HOME}/lib/guava-19.0.jar && \
    cp ${HADOOP_HOME}/share/hadoop/common/lib/guava-27.0-jre.jar ${HIVE_HOME}/lib && \
    cp ${HADOOP_HOME}/share/hadoop/tools/lib/hadoop-aws-${HADOOP_VERSION}.jar ${HIVE_HOME}/lib && \
    cp ${HADOOP_HOME}/share/hadoop/tools/lib/aws-java-sdk-bundle-1.11.375.jar ${HIVE_HOME}/lib

# Copy Hive Metastore configuration and entrypoint script
COPY metastore-site.xml ${HIVE_HOME}/conf/
COPY entrypoint.sh /entrypoint.sh

# Set up user permissions for Hive
RUN groupadd -r hive --gid=1000 && \
    useradd -r -g hive --uid=1000 -d ${HIVE_HOME} hive && \
    chown hive:hive -R ${HIVE_HOME} && \
    chown hive:hive /entrypoint.sh && chmod +x /entrypoint.sh

# Set working directory to Hive Metastore
WORKDIR /opt/metastore

# Expose Hive Metastore port
EXPOSE 9083

# Run the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
