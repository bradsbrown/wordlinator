#!/bin/bash

RELOAD=""
if $DEBUG; then
    RELOAD="--reload"
fi
poetry run gunicorn $RELOAD -b "0.0.0.0:8050" "wordlinator.web:server"
