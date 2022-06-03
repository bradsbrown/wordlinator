FROM python:3.10

RUN apt update && apt install libpq-dev

COPY . .

RUN python -m pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install

CMD ./serve.sh
