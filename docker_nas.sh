#!/bin/bash

DOCKER_CONTEXT=nas docker ps | grep wordlinator && DOCKER_CONTEXT=nas docker stop wordlinator || true
DOCKER_CONTEXT=nas DB_PORT=49420 DB_HOST="localhost" ./docker.sh "$@" --network=host
