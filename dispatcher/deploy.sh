#!/usr/bin/env bash

git pull
docker-compose -f docker-compose2.yml up --build -d
