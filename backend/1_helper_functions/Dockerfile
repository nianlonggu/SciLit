# start from base
FROM base_image_deep_learning as base

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/src
COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD [ "bash", "run_service.sh" ]