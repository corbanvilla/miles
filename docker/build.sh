#!/bin/bash

set -e

#docker build .. -f Dockerfile-index -t animcogn/miles:index-0.2
#
#docker build .. -f Dockerfile-predict -t animcogn/miles:predict-0.2
#
#docker build .. -f Dockerfile-train -t animcogn/miles:train-0.2

docker build .. -f Dockerfile-api -t animcogn/miles:api-0.2

#docker build .. -f Dockerfile-slack -t animcogn/miles:slack-0.2

#docker image push animcogn/miles:index-0.2
#
#docker image push animcogn/miles:predict-0.2
#
#docker image push animcogn/miles:train-0.2

docker image push animcogn/miles:api-0.2

#docker image push animcogn/miles:slack-0.2
