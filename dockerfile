FROM alpine

COPY . /app
COPY src /app

WORKDIR /app

RUN apk add python3
RUN python3 -m pip install uv && uv sync --lock

EXPOSE 8501