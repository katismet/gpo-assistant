FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y build-essential libffi-dev libpango-1.0-0 libpangoft2-1.0-0 libjpeg62-turbo && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install -U pip && pip install -e .
COPY . .
CMD ["python","-u","-m","app.telegram.bot"]
