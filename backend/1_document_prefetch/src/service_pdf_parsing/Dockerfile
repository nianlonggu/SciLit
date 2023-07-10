FROM document_prefetch_base as base

# Set Environment Variable
ENV JAVA_TOOL_OPTIONS="-Dhttps.protocols=TLSv1.2"
ENV PDF2JSON_HOME="/app/src/s2orc-doc2json"
ENV ROOT_DATA_PATH="/app/data"

# install system-wide deps for python and node
RUN apt-get -yqq update && \
    apt-get -yqq install openjdk-8-jdk 
    
SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/src
COPY ./requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app/src/s2orc-doc2json
COPY ./s2orc-doc2json/ .
RUN python setup.py develop

WORKDIR $HOME
RUN wget https://github.com/kermitt2/grobid/archive/0.6.1.zip && \
    unzip 0.6.1.zip && \
    rm 0.6.1.zip

WORKDIR $HOME/grobid-0.6.1
RUN ./gradlew clean install && \
    cp $PDF2JSON_HOME/doc2json/grobid2json/grobid/config.yaml $HOME/grobid-0.6.1/grobid-service/config/config.yaml && \
    cp $PDF2JSON_HOME/doc2json/grobid2json/grobid/grobid.properties $HOME/grobid-0.6.1/grobid-home/config/grobid.properties


WORKDIR /app/src
COPY ./Dockerfile .

WORKDIR /app/src/services
COPY ./services/ .

# start app
# will use the pure bash, ignoring the bash environment specified by SHELL command above
CMD [ "bash", "./start_service.sh" ] 