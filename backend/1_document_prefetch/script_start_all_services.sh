#!/bin/bash

####### 
# NUM_PROCESSES: number process that is used to build the inverted index and embedding index. To fully utilize CPU cores on a large corpus like S2ORC, set NUM_PROCESSES to 2 times of the number of CPU cores

# NUM_EMBEDDING_INDEX_SHARDS:  Number of shardded embedding index files. When using CPU-approximate nearest neighbor search (USE_GPU=0), set NUM_EMBEDDING_INDEX_SHARDS to a large value (e.g., 2 times of the number of CPU cores). When using GPU brute-force nearest neighbor search (USE_GPU=1), set NUM_EMBEDDING_INDEX_SHARDS to the number of available GPUs

# EMBEDDING_INDEX_PRECISION: used for low-precision GPU BFNN. Available choices: bool, int4, int8, float32  . When USE_GPU=0 or no GPU is available, EMBEDDING_INDEX_PRECISION will be switched to float32 automatically


#### prefetch server on arXiv
DATA_PATH=$PWD/data/arXiv NUM_PROCESSES=10 NUM_EMBEDDING_INDEX_SHARDS=20 PRIVATE=0 USE_GPU=0 EMBEDDING_INDEX_PRECISION=int4 SERVICE_SUFFIX=arxiv docker-compose -f docker-compose-document-prefetch.yaml -p document_prefetch_arxiv  up --build -d


#### prefetch server on PMCOA
DATA_PATH=$PWD/data/PMCOA NUM_PROCESSES=10 NUM_EMBEDDING_INDEX_SHARDS=20 PRIVATE=0 USE_GPU=0 EMBEDDING_INDEX_PRECISION=int4  SERVICE_SUFFIX=pmcoa docker-compose -f docker-compose-document-prefetch.yaml -p document_prefetch_pmcoa  up --build -d


#### prefetch server on S2ORC
DATA_PATH=$PWD/data/S2ORC NUM_PROCESSES=10 NUM_EMBEDDING_INDEX_SHARDS=20 PRIVATE=0 USE_GPU=0 EMBEDDING_INDEX_PRECISION=int4  SERVICE_SUFFIX=s2orc docker-compose -f docker-compose-document-prefetch.yaml -p document_prefetch_s2orc  up --build -d
