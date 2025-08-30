# Base image: OpenJDK 21 for running Trino 434+ (requires Java 17.0.5+ minimum)
FROM openjdk:21-jdk-slim

# Define Trino version (updated to 434 for hive-hadoop2 compatibility)
ARG TRINO_VERSION=434

# Set environment variables
ENV TRINO_HOME=/opt/trino
ENV PATH=$TRINO_HOME/server/bin:$PATH

# Install necessary tools and dependencies, including Python
RUN apt-get update && \
    apt-get install -y curl wget tar uuid-runtime python3 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

# Create necessary directories
WORKDIR /opt
RUN mkdir -p $TRINO_HOME/server $TRINO_HOME/server/etc $TRINO_HOME/server/catalog $TRINO_HOME/data

# Download and install Trino (0.375+)
RUN wget https://repo1.maven.org/maven2/io/trino/trino-server/${TRINO_VERSION}/trino-server-${TRINO_VERSION}.tar.gz && \
    tar xvf trino-server-${TRINO_VERSION}.tar.gz -C $TRINO_HOME/server --strip-components=1 && \
    rm trino-server-${TRINO_VERSION}.tar.gz

# Copy configuration files to /opt/trino/server/etc/
COPY etc/node.properties $TRINO_HOME/server/etc/node.properties
COPY etc/config.properties $TRINO_HOME/server/etc/config.properties
COPY etc/jvm.config $TRINO_HOME/server/etc/jvm.config

# Copy catalog configuration files to /opt/trino/server/etc/catalog/
COPY etc/catalog/delta.properties $TRINO_HOME/server/etc/catalog/delta.properties
COPY etc/catalog/hive.properties $TRINO_HOME/server/etc/catalog/hive.properties

# Download and install Trino CLI (0.375+)
RUN wget https://repo1.maven.org/maven2/io/trino/trino-cli/${TRINO_VERSION}/trino-cli-${TRINO_VERSION}-executable.jar -O /opt/trino/server/bin/trino \
    && chmod +x /opt/trino/server/bin/trino

# Expose Trino HTTP port
EXPOSE 8443

# Set working directory to Trino home
WORKDIR $TRINO_HOME/server

# Run Trino server using launcher script
CMD ["bin/launcher", "run"]
