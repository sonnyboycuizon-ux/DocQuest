#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

python_version=""
if command -v python3 &>/dev/null; then
    python_version="python3"
elif command -v python &>/dev/null; then
    python_version="python"
else
    echo "Python is not installed. Aborting."
    exit 1
fi

pip install --upgrade pip
pip install -r requirements.txt

$python_version manage.py collectstatic --noinput
$python_version manage.py migrate --noinput
$python_version manage.py create_superuser || true
