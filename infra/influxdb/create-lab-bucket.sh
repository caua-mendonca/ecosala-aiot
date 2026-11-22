#!/bin/bash
# Executado pelo container do InfluxDB após o setup inicial: cria o bucket
# separado "lab" para a amostra dos dados sintéticos (não mistura com o ao vivo).
set -e
influx bucket create --name lab --org "${DOCKER_INFLUXDB_INIT_ORG}" --retention 30d \
  --token "${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}" || true
