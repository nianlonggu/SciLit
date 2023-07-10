#!/bin/bash

docker-compose -f docker-compose-build-database-arXiv.yaml up --build 

docker-compose -f docker-compose-build-database-PMCOA.yaml up --build 

