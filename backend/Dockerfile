# Imagem única para todos os serviços Python do EcoSala (API, gateway, gravador,
# inferência, worker de IA, simulador e rabbit-init). Cada serviço escolhe o
# comando no docker-compose.yml.
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# usuário sem privilégios (containers da aplicação não rodam como root)
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /models /data && chown -R app:app /models /data

COPY --chown=app:app . .
USER app

CMD ["python", "-m", "ecosala_common.health"]
