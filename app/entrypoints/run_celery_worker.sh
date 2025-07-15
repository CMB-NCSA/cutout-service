#!/bin/bash

set -euo pipefail

QUEUES=$1

cd "${APP_ROOT_DIR:-/opt}/app"

bash entrypoints/wait-for-it.sh ${DATABASE_HOST}:${DATABASE_PORT:-5432} --timeout=0
bash entrypoints/wait-for-it.sh ${MESSAGE_BROKER_HOST}:${MESSAGE_BROKER_PORT:-5672} --timeout=0
bash entrypoints/wait-for-it.sh ${API_SERVER_HOST}:${API_SERVER_PORT} --timeout=0

# Start worker
if [[ $DEV_MODE == "true" ]]; then
    watchmedo auto-restart --directory=./ --pattern=*.py --recursive -- \
    celery -A cutout worker \
        --queues $QUEUES \
        --loglevel ${CELERY_LOG_LEVEL:-DEBUG} \
        --concurrency ${CELERY_CONCURRENCY:-4}
else
    celery -A cutout worker \
        --queues $QUEUES \
        --loglevel ${CELERY_LOG_LEVEL:-INFO} \
        --concurrency ${CELERY_CONCURRENCY:-4}
fi
