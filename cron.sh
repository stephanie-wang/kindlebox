#!/bin/bash
source /var/www/kindlebox/env/bin/activate
export PROD=1
python /var/www/kindlebox/run.py tasks
