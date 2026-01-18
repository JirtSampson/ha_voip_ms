ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and dependencies
RUN apk add --no-cache python3 py3-pip

# Copy application files
COPY run.py /
COPY voipms_client.py /
COPY mqtt_publisher.py /
COPY audio_server.py /
COPY requirements.txt /

# Install Python packages
RUN pip3 install --no-cache-dir -r /requirements.txt

# Run the application
CMD ["python3", "/run.py"]
