#!/bin/bash

source activate my_env

python unzip_files.py
python build_raw_jsonl_database.py
python build_normalized_sqlite_database.py 