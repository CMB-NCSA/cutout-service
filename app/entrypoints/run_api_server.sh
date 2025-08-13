#!/bin/bash

set -euo pipefail

# Migrations should be created manually by developers and committed with the source code repo.
# Set the MAKE_MIGRATIONS env var to a non-empty string to create migration scripts
# after changes are made to the Django ORM models.
if [ "$MAKE_MIGRATIONS" == "true" ]; then
  echo "Generating database migration scripts..."
  python manage.py makemigrations --no-input
  exit 0
fi

## Initialize Django database and static files
##
cd "${APP_ROOT_DIR:-/opt}/app"
bash entrypoints/wait-for-it.sh ${DATABASE_HOST}:${DATABASE_PORT} --timeout=0

echo "Running initialization script..."
bash entrypoints/django_init.sh
echo "Django database initialization complete."

if [ "$DATA_INIT" == "true" ]; then
  echo "Initializing application data..."
  bash entrypoints/data_init.sh
fi

# Start server
cd "${APP_ROOT_DIR:-/opt}/app"
if [[ $DEV_MODE == "true" ]]; then
  echo "Running development Django server..."
  set -x
  python manage.py runserver 0.0.0.0:${API_SERVER_PORT}
else
  ## Run Django server via Gunicorn
  ## see https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/uvicorn/
  set -x
  uvicorn \
  --host=0.0.0.0 \
  --port=${API_SERVER_PORT} \
  --workers=2 \
  --log-level=info \
  cutout.asgi:application
fi
