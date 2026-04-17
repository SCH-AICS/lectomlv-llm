#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until python -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('${POSTGRES_HOST:-postgres}', int('${POSTGRES_PORT:-5432}')))
    s.close()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready."

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting: $@"
exec "$@"
