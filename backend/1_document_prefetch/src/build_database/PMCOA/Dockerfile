FROM paper_database_manager as base

ENV COLLECTION="PMCOA"
ENV ROOT_DATA_PATH=/app/data
## Here setting the default number of processes to 16, and this can be overwritten when calling docker run by setting -e (or --env)
ENV NUM_PROCESSES=16

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/src
COPY . .

RUN pip install -r requirements.txt

## Note: when calling docker run, one must map the host machine's volume to /app/data
## The host volume is expected to contain all the data needed for the search engine
CMD [ "bash", "run.sh" ]


######## Required Environment Variables #########
# NUM_PROCESSES

######## Monting Volume ######
# /app/data