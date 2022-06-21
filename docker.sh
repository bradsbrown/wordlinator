#!/bin/bash

docker build -t wordlinator:latest .

if [ "$1" == "--debug" ]; then
    shift
    echo "Running debug mode..."
    docker run -d --rm -p 8050:8050 -e DASH_DEBUG=true -e DB_PORT -e DB_HOST -e DB_PASS "$@" --name wordlinator wordlinator:latest
else
    docker run -d --rm -p 8050:8050 -e DB_PORT -e DB_HOST -e DB_PASS "$@" --name wordlinator wordlinator:latest
fi
