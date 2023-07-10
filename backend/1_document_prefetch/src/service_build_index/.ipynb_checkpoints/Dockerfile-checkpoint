FROM document_prefetch_base as base


ENV ROOT_DATA_PATH=/app/data

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/src

COPY . .

RUN pip install -r requirements.txt

CMD [ "bash", "run_service.sh" ]

######## Required Environment Variables #########
## NUM_EMBEDDING_INDEX_SHARDS
## NUM_INVERTED_INDEX_SHARDS

######## Monting Volume ######
## /app/data