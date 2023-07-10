#!/bin/bash


#### prefetch server on arXiv
DATA_PATH=$PWD/data/arXiv NUM_PROCESSES=10 PRIVATE=0 USE_GPU=0 PORT=8021 SERVICE_SUFFIX=arxiv docker-compose -f docker-compose-document-prefetch.yaml -p document_prefetch_arxiv  up --build -d


#### prefetch server on PMCOA
DATA_PATH=$PWD/data/PMCOA NUM_PROCESSES=10 PRIVATE=0 USE_GPU=0 PORT=8022 SERVICE_SUFFIX=pmcoa docker-compose -f docker-compose-document-prefetch.yaml -p document_prefetch_pmcoa  up --build -d
