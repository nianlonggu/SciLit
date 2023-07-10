#!/bin/bash

screen -dmS grobid bash -c 'cd $HOME/grobid-0.6.1 && ./gradlew run'

source activate my_env

cd /app/src/services && gunicorn -k gthread -w 4 --threads 16 --backlog 2048 pdf_parsing_service:app -b 0.0.0.0:8061 &

## wait for the pdf parsing service to be ready
sleep 30

cd /app/src/build_database

python convert_pdf_to_S2ORC_json.py
python build_normalized_sqlite_database.py
