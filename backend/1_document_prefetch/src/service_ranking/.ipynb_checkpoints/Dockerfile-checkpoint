FROM document_prefetch_base as base

ENV ROOT_DATA_PATH=/app/data

WORKDIR /app/src

COPY . .

SHELL [ "conda", "run", "-n", "my_env", "/bin/bash", "-c" ]

RUN pip install -r requirements.txt && \
    python -m spacy download en_core_web_sm


CMD [ "bash", "run_service.sh" ]


##### -e #####
# IS_PRIVATE_SERVER
# USE_GPU

##### -v #####
# Host data foler : /app/data