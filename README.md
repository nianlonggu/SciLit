# SciLit: A Platform for Joint Scientific Literature Discovery, Summarization and Citation Generation

A comprehensive full-stack solution has been developed for the creation of a large-scale search engine tailored for scientific papers. This system incorporates natural language processing capabilities, facilitating tasks such as citation recommendations, document summarization, and generation of citation sentences.

LIVE DEMO: https://scilit.vercel.app/

PAPER: https://aclanthology.org/2023.acl-demo.22.pdf

![](frontend/screenshots/frontend.png)
 
## Installation
### Install Docker
This step is NOT needed if Docker engine has already been installed.
#### Install Docker engine
#####  On Ubuntu
```bash
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world
```
See detailed installation instruction on [Docker Engine Installation (Ubuntu)](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)
##### On Debian
```bash
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world
```
Please see detailed installation instruction on [Docker Engine Installation (Debian)](https://docs.docker.com/engine/install/debian/#install-using-the-repository)



#### Add current user into docker group to avoid explicitly use sudo
```bash
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
sudo setfacl -m user:$USER:rw /var/run/docker.sock

## test if it works
docker run hello-world
```
#### Change the default folder of docker (optional)
By default docker save its cache files and logs to /var/lib/docker. Sometimes this can be problematic due to the limited space of /var/lib. In this case, we need to change this default folder to a custom folder with a large space. Please refer https://www.ibm.com/docs/en/z-logdata-analytics/5.1.0?topic=compose-relocating-docker-root-directory for how to change the root directory of docker.

#### Configure GPU support for Docker (optional, only for GPU-machine)
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
```
Then resolve the package conflicting error before running "apt-get update": E: Conflicting values set for option Signed-By regarding source ... (See https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/troubleshooting.html#conflicting-values-set-for-option-signed-by-error-when-running-apt-update for the details.)
```
sudo rm $(grep -l "nvidia.github.io" /etc/apt/sources.list.d/* | grep -vE "/nvidia-container-toolkit.list\$")
```
Then install nvidia-container-toolkit and restart docker
```bash
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```
Test if GPU can be detected within docker containers
```bash
docker run --rm --runtime=nvidia --gpus all nvidia/cuda:11.6.2-base-ubuntu20.04 nvidia-smi
```
See https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#setting-up-docker for more details.

#### Install Docker Compose
```bash
pip install docker-compose
```

### Install Node.js
```bash
sudo apt update
## make sure the node version is 20.x
curl -sL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs
```
check node version
```bash
node -v
```

## Prepare Raw Corpus
Here we demonstrated building the search engine on papers from S2ORC, PubMed Open Access (PMCOA) and arXiv.
### S2ORC
S2ORC can be accessed via [semantic scholar api](https://www.semanticscholar.org/product/api). Here we only download a tiny subset to demonstrate the pipeline. 

```bash
mkdir -p backend/1_document_prefetch/data/S2ORC/raw/metadata
mkdir -p backend/1_document_prefetch/data/S2ORC/raw/pdf_parses
wget -P backend/1_document_prefetch/data/S2ORC/raw/metadata https://huggingface.co/scieditor/example_data_S2ORC/raw/main/metadata/metadata_0.jsonl
wget -P backend/1_document_prefetch/data/S2ORC/raw/metadata https://huggingface.co/scieditor/example_data_S2ORC/raw/main/metadata/metadata_1.jsonl
wget -P backend/1_document_prefetch/data/S2ORC/raw/pdf_parses https://huggingface.co/scieditor/example_data_S2ORC/resolve/main/pdf_parses/pdf_parses_0.jsonl
wget -P backend/1_document_prefetch/data/S2ORC/raw/pdf_parses https://huggingface.co/scieditor/example_data_S2ORC/resolve/main/pdf_parses/pdf_parses_1.jsonl

```
This is how the files are organized:
```
backend/1_document_prefetch/data/S2ORC/
└── raw
    ├── metadata
    │   ├── metadata_0.jsonl
    │   └── metadata_1.jsonl
    └── pdf_parses
        ├── pdf_parses_0.jsonl
        └── pdf_parses_1.jsonl
```


### PMCOA
We can download the .tar.gz files from the official FTP service https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/, and put the files into the folder:
```
backend/1_document_prefetch/data/PMCOA/raw/tar_gz/
```
Here we only download one .tar.gz file oa_comm_xml.incr.2023-07-06.tar.gz as an example:
```bash
## create the folder if not exist
mkdir -p backend/1_document_prefetch/data/PMCOA/raw/tar_gz/
## download the tar.gz file
wget -P backend/1_document_prefetch/data/PMCOA/raw/tar_gz https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/oa_comm_xml.incr.2023-07-06.tar.gz

```
This is how the files are organized:
```
backend/1_document_prefetch/data/
└── PMCOA
    └── raw
        └── tar_gz
            └── oa_comm_xml.incr.2023-07-06.tar.gz
```

### arXiv
First we need to install "gsutil" to to able to bulk download arXiv PDFs. For detail, please refer to https://cloud.google.com/storage/docs/gsutil_install#sdk-install

After gsutil has been installed and initiated, we can bulk download arXiv PDFs from google cloud storage. See https://www.kaggle.com/datasets/Cornell-University/arxiv for official instructions.

Here we only download a small percentage of the PDF published within July 2023.
```bash
mkdir -p backend/1_document_prefetch/data/arXiv/raw/pdf/2307

gsutil -m cp -r gs://arxiv-dataset/arxiv/arxiv/pdf/2307/2307.00* backend/1_document_prefetch/data/arXiv/raw/pdf/2307/

```
This is how the files are organized:
```
backend/1_document_prefetch/data/arXiv/
└── raw
    └── pdf
        └── 2307
```

## Build Paper Database 

Convert the corpus from the original format (tar.gz for PMCOA and PDF for arXiv) to a unified SQLite paper database, in which each record represents a paper and follows the same JSON schema. This is used for search engine for existing collections.
```bash
BASE_DIR=$PWD
cd backend/1_document_prefetch/ && bash script_build_all_databases.sh
cd $BASE_DIR
```

Running this script automatically builds the databases for PMCOA and arXiv. The dockerized code base for building databases for these two collections is available at **backend/1_document_prefetch/src/build_database/**

## Start Backend Services
If the host machine does not have GPUs, before running the following commands, first comment out the line "runtime: nvidia" (by adding a "#" before "runtime") in the following docker-compose.yaml files:

[backend/1_document_prefetch/docker-compose-document-prefetch.yaml#L38](backend/1_document_prefetch/docker-compose-document-prefetch.yaml#L38)

[backend/3_citation_generation/docker-compose.yaml#L9](backend/3_citation_generation/docker-compose.yaml#L9)

[backend/3_document_reranking/docker-compose.yaml#L9](backend/3_document_reranking/docker-compose.yaml#L9)

[backend/3_extractive_summarization/docker-compose.yaml#L9](backend/3_extractive_summarization/docker-compose.yaml#L9)

Note: Running the SciBERT-based document reranking on CPU can be slow, please consider skipping reranking in this case by setting "requires_reranking" to False in line:
[backend/4_document_search_overall/service.py#L267](backend/4_document_search_overall/service.py#L267)

Once "runtime: nvidia" is commented out, the environment "USE_GPU" is deactivated automatically, so there is no need to change the environment variables.

Run the following commands to start the backend services:


```bash
#### We denote BASE_DIR as the root path of this repo, where this README is located.
BASE_DIR=$PWD

#### create "common_network" if it does not exist
NETWORK_NAME="common_network"; if ! docker network ls --format "{{.Name}}" | grep -q "^${NETWORK_NAME}$"; then docker network create ${NETWORK_NAME}; fi
cd $BASE_DIR/backend/0_base_image_deep_learning && docker-compose up --build
cd $BASE_DIR/backend/1_document_prefetch && bash script_start_all_services.sh
cd $BASE_DIR/backend/1_helper_functions && docker-compose up --build -d
cd $BASE_DIR/backend/2_fast_metadata_search && docker-compose up --build -d
cd $BASE_DIR/backend/2_paper_database_service && docker-compose up --build -d
cd $BASE_DIR/backend/3_citation_formating && docker-compose up --build -d
cd $BASE_DIR/backend/3_citation_generation && docker-compose up --build -d
cd $BASE_DIR/backend/3_document_reranking && docker-compose up --build -d
cd $BASE_DIR/backend/3_extractive_summarization && docker-compose up --build -d
cd $BASE_DIR/backend/4_document_search_overall && docker-compose up --build -d
cd $BASE_DIR/backend/5_title_generic_search && docker-compose up --build -d
cd $BASE_DIR/backend/final_api_gateway && docker-compose up --build -d

cd $BASE_DIR

```

By default, port 8060 is used by the final API gateway to communicate with the frontend or API developers.
This PORT can be changed in the [docker-compose.yaml file of the api gateway](backend/final_api_gateway/docker-compose.yaml).

Please refer to the [API documentation](backend/Documentation%20of%20Microservices.md) for details on the usage of all backend APIs for developing a scientific document search engine enriched with NLP functions.

## Start Frontend Service (the SciLit webpage)
Here we suppose that the backend is running on the same local machine and is listening to the PORT 8060.
If the backend is running on a remote server (e.g., google cloud VM), please replace "localhost" with the server's IP address.

```bash
BASE_DIR=$PWD
cd $BASE_DIR/frontend/SciLit-React

npm install
export REACT_APP_NLP_SERVER_ADDRESS=http://localhost:8060; npm start

```

Now the frontend service (React based) is running on PORT 3000. You can now open your browser and go to http://localhost:3000 to use SciLit!

## Troubleshoot
### Proxy Issue
This installation pipeline is not suitable on a host machine with proxy.


## Reference
When using our code or models for your application, please cite the following paper:
```
@inproceedings{gu-hahnloser-2023-scilit,
    title = "{S}ci{L}it: A Platform for Joint Scientific Literature Discovery, Summarization and Citation Generation",
    author = "Gu, Nianlong  and
      Hahnloser, Richard H.R.",
    booktitle = "Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 3: System Demonstrations)",
    month = jul,
    year = "2023",
    address = "Toronto, Canada",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2023.acl-demo.22",
    pages = "235--246",
    abstract = "Scientific writing involves retrieving, summarizing, and citing relevant papers, which can be time-consuming processes. Although in many workflows these processes are serially linked, there are opportunities for natural language processing (NLP) to provide end-to-end assistive tools. We propose SciLit, a pipeline that automatically recommends relevant papers, extracts highlights, and suggests a reference sentence as a citation of a paper, taking into consideration the user-provided context and keywords. SciLit efficiently recommends papers from large databases of hundreds of millions of papers using a two-stage pre-fetching and re-ranking literature search system that flexibly deals with addition and removal of a paper database. We provide a convenient user interface that displays the recommended papers as extractive summaries and that offers abstractively-generated citing sentences which are aligned with the provided context and which mention the chosen keyword(s). Our assistive tool for literature discovery and scientific writing is available at https://scilit.vercel.app",
}
```

