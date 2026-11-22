#!/bin/sh
# Baixa o modelo (só na primeira vez) e o deixa pré-carregado na memória.
set -e
export OLLAMA_HOST="${OLLAMA_HOST:-ollama:11434}"
echo "Baixando/verificando o modelo ${OLLAMA_MODEL}..."
ollama pull "${OLLAMA_MODEL}"
echo "Pré-carregando o modelo na memória (keep_alive 24h)..."
ollama run "${OLLAMA_MODEL}" "Responda apenas: ok" --keepalive 24h > /dev/null
echo "Modelo ${OLLAMA_MODEL} pronto."
