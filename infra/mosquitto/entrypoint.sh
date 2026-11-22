#!/bin/sh
# Gera o arquivo de senhas (hash) a partir das variáveis do .env a cada subida.
set -e
PASSWD=/mosquitto/data/passwd
umask 077
rm -f "$PASSWD"
touch "$PASSWD"
mosquitto_passwd -b "$PASSWD" device "$MQTT_DEVICE_PASSWORD"
mosquitto_passwd -b "$PASSWD" gateway "$MQTT_GATEWAY_PASSWORD"
chown mosquitto:mosquitto "$PASSWD" /mosquitto/data
chmod 0700 "$PASSWD"
exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
