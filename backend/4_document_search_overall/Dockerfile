# start from base
FROM base_image_deep_learning as base

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/models/sent2vec
# Download necessary sent2vec model checkpoint
RUN python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='scieditor/document-prefetch-sent2vec', filename='model_256.bin', local_dir='/app/models/sent2vec')"
# Download pretrained SciBERT checkpoint
RUN python -c "from transformers import BertTokenizerFast, BertForNextSentencePrediction; model_path = 'scieditor/document-reranking-scibert'; tokenizer = BertTokenizerFast.from_pretrained(model_path); model = BertForNextSentencePrediction.from_pretrained(model_path)"

WORKDIR /app/src
COPY . .

CMD [ "bash", "run_service.sh" ]