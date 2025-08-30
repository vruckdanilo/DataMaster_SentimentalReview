# Inherit from spark-base
ARG SPARK_BASE_IMAGE=spark-base:latest
FROM ${SPARK_BASE_IMAGE}

# Set environment variables for Spark Master
ENV SPARK_MASTER_PORT=7077
ENV SPARK_MASTER_UI_PORT=8082
ENV SPARK_MASTER_LOG_DIR=/var/logs/spark

# Copy the start-master script
COPY start-master.sh .

# Give executable permission to the start script
RUN chmod +x start-master.sh

# Expose necessary ports for the Spark Master
EXPOSE 8082 7077 6066

# Command to run the Spark Master
CMD ["./start-master.sh"]
