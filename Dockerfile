FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY email_validator_tool.py web_app.py server.py ./
COPY templates ./templates
COPY static ./static
RUN useradd --create-home appuser && mkdir /app/server-data && chown appuser:appuser /app/server-data
USER appuser
EXPOSE 8080
CMD ["python", "server.py"]
