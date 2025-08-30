# Inherit from spark-base
ARG SPARK_BASE_IMAGE=spark-base:latest
FROM ${SPARK_BASE_IMAGE}

# Set environment variables for Spark Worker
ENV SPARK_WORKER_UI_PORT=8081
ENV SPARK_WORKER_LOG_DIR=/var/logs/spark

# Copy the start-worker script
COPY start-worker.sh .

# Give executable permission to the start script
RUN chmod +x start-worker.sh

# Expose necessary ports for the Spark Worker
EXPOSE 8081

# Command to run the Spark Worker
CMD ["./start-worker.sh"]
