#!/bin/bash

source activate my_env

python build_raw_sqlite_database.py
python build_normalized_sqlite_database.py