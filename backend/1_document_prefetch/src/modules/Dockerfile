# start from base
FROM ubuntu:22.04

# Set Environment Variable
ENV HOME="/root"
ENV SENT2VEC_MODEL_FOLDER="/app/models/sent2vec"
ENV SENT2VEC_MODEL_PATH="/app/models/sent2vec/model_256.bin"
ENV PACKAGES_PATH="/app/packages"
ENV PYTHONPATH=${PYTHONPATH}:${PACKAGES_PATH}


# install system-wide deps for python and node
RUN apt-get -yqq update && \
    apt-get -yqq install software-properties-common curl wget zip screen git gcc build-essential

# Install Miniconda
RUN curl -LO https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash Miniconda3-latest-Linux-x86_64.sh -p /miniconda -b && \
    rm Miniconda3-latest-Linux-x86_64.sh
ENV PATH=/miniconda/bin:${PATH}

# Create a Python 3.10 environment
RUN conda create -n my_env python=3.10
# Activate the environment
# For the following commands in this Dockerfile, use the bash shell inside the my_env conda environment.
SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]


# # Add customized python modules
WORKDIR ${PACKAGES_PATH}/modules
COPY ./requirements.txt .

RUN conda install -c conda-forge cupy cudatoolkit=11.7 && \
    pip install -r requirements.txt

# Download necessary sent2vec model checkpoint
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='scieditor/document-prefetch-sent2vec', filename='model_256.bin', local_dir='${SENT2VEC_MODEL_FOLDER}')"

WORKDIR ${PACKAGES_PATH}/modules
COPY . .
