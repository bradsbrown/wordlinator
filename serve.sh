#!/bin/bash

poetry run gunicorn -b "127.0.0.1:8050" "wordlinator.web:server"
