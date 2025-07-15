#!/bin/env bash
set -e

bash /wait-for-it.sh ${API_SERVER_HOST}:${API_SERVER_PORT} --timeout=0
bash /wait-for-it.sh ${FLOWER_HOST}:${FLOWER_PORT} --timeout=0

export DOLLAR="$"
envsubst < /etc/nginx/nginx.conf.tpl > /etc/nginx/nginx.conf
cat /etc/nginx/nginx.conf
