#!/bin/bash

docker run --name my-redis -d -p 6379:6379 redis:latest

if [ $? -eq 0 ]; then
    echo "Redis container started successfully"
else
    echo "Failed to start Redis container"
fi
