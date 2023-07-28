FROM paper_database_manager as base

ENV ROOT_DATA_PATH=/app/data

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/src
COPY . .

RUN pip install -r requirements.txt

## Note: when calling docker run, one must map the host machine's volume to /app/data
## The host volume is expected to contain all the data needed for the search engine
CMD [ "bash", "run.sh" ]
