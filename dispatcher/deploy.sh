#!/usr/bin/env bash

git pull
export SYSTEM_PASSWORD=`pwgen -Bs1 12`
docker-compose -f docker-compose.yml up --build -d
