# start from base
FROM ubuntu:22.04

# Set Environment Variable
ENV HOME="/root"
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

RUN conda install pytorch torchvision torchaudio pytorch-cuda=11.7 -c pytorch -c nvidia && \
    conda install -c conda-forge cupy cudatoolkit=11.7
    
WORKDIR /app/installation/temp
COPY . .

RUN pip install -r requirements.txt && \ 
    python -m spacy download en_core_web_sm
