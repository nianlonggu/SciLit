FROM document_prefetch_base as base

ENV ROOT_DATA_PATH=/app/data

WORKDIR /app/src

COPY . .

SHELL [ "conda", "run", "-n", "my_env", "/bin/bash", "-c" ]

RUN pip install -r requirements.txt 

CMD [ "bash", "run_service.sh" ]


##### -e #####

##### -v #####
# Host data foler : /app/data