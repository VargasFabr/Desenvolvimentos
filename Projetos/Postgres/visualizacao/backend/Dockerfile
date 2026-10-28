FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] psycopg2-binary openpyxl pydantic python-multipart

COPY visualizacao/backend/app /app/app
COPY lib /dados/lib

ENV PYTHONPATH=/dados
ENV DADOS_ROOT=/dados

EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
