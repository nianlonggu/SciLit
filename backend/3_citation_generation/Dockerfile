# start from base
FROM base_image_deep_learning as base

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/models/
# Download necessary model checkpoint
RUN python -c "from transformers import T5Tokenizer, T5ForConditionalGeneration; model_path = 'scieditor/citation-generation-t5'; tokenizer = T5Tokenizer.from_pretrained(model_path); model = T5ForConditionalGeneration.from_pretrained(model_path)"

WORKDIR /app/src
COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD [ "bash", "run_service.sh" ]