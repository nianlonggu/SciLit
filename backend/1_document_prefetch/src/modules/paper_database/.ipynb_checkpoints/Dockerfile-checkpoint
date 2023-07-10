# start from a miniconda base
FROM continuumio/miniconda3

# Set Environment Variable
ENV PACKAGES_PATH="/app/packages"
ENV PYTHONPATH=${PYTHONPATH}:${PACKAGES_PATH}

# Create a Python 3.10 environment
RUN conda create -n my_env python=3.10
# Activate the environment
# For the following commands in this Dockerfile, use the bash shell inside the my_env conda environment.
SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

# Add customized python modules
WORKDIR ${PACKAGES_PATH}/modules/paper_database
COPY . .

RUN pip install -r requirements.txt

