#!/bin/bash

screen -dmS grobid bash -c 'cd $HOME/grobid-0.6.1 && ./gradlew run'

source activate my_env
### This service is for pdf indexing, and it is threaded, one query per time
python pdf_indexing_service.py &

### This service is for fast concurrent pdf parsing
gunicorn -k gthread -w 4 --threads 16 --backlog 2048 pdf_parsing_service:app -b 0.0.0.0:8061 &

wait

# python pdf_parsing_service.py
# here we use gunicorn, which has a better control of incoming request than Flask
# -k gthread : a working mode
# -w 4 : number of workers
# --threads 16 :   w x threads, total number of requests processed at the same time. Since in grobid .yml the maximum connection is 72, w x threads should not be large than that value in this case
# backlog: the queue size, default 2048



