#!/bin/bash

set -e

docker build .. -f Dockerfile-index -t animcogn/miles:index-0.1

docker build .. -f Dockerfile-predict -t animcogn/miles:predict-0.1

docker build .. -f Dockerfile-train -t animcogn/miles:train-0.1

docker image push animcogn/miles:index-0.1

docker image push animcogn/miles:predict-0.1

docker image push animcogn/miles:train-0.1