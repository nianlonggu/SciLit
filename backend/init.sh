#!/bin/bash

BASE_DIR=$PWD

#### create common_network if it does not exist
NETWORK_NAME="common_network"; if ! docker network ls --format "{{.Name}}" | grep -q "^${NETWORK_NAME}$"; then docker network create ${NETWORK_NAME}; fi


#### Build the SqliteDatabse given the raw files of the collections
## Here we use the tar.gz files from PubMed Open Access: https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/ to build the data collection "PMCOA", and PDFs from https://www.kaggle.com/datasets/Cornell-University/arxiv to build the collection "arXiv"

cd $BASE_DIR/1_document_prefetch
bash script_build_all_databases.sh
