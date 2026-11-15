FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 4000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "4000"]
