FROM python:3.14-slim
WORKDIR /app
COPY requirements-connected.txt .
RUN pip install --no-cache-dir -r requirements-connected.txt
COPY ha ./ha
COPY web ./web
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 ha
USER ha
EXPOSE 8080
CMD ["sh", "-c", "exec python -m ha.connected.server --host 0.0.0.0 --port 8080 --behind-https-proxy --origin \"$HA_PUBLIC_ORIGIN\""]
