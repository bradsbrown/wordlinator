FROM python:3.10

RUN apt update && apt install libpq-dev

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock

RUN python -m pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install


COPY wordlinator/ wordlinator/

EXPOSE 8050

CMD gunicorn --workers 8 -b "0.0.0.0:8050" "wordlinator.web:server"
