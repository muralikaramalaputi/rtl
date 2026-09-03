#!/usr/bin/env bash

apt-get update
apt-get install -y iverilog

pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate