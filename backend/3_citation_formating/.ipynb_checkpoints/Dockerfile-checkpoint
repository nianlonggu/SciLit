# start from base
FROM base_image_deep_learning as base

SHELL ["conda", "run", "-n", "my_env", "/bin/bash", "-c"]

WORKDIR /app/src

COPY . .

CMD [ "bash", "run_service.sh" ]