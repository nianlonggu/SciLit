# start from base
FROM base_image_deep_learning as base

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/models/
# Download necessary model checkpoint
RUN python -c "from huggingface_hub import snapshot_download; import shutil; from glob import glob; model_folder = '/app/models/'; snapshot_download('scieditor/extractive-summarization', local_dir = model_folder )"

WORKDIR /app/src
COPY . .

CMD [ "bash", "run_service.sh" ]