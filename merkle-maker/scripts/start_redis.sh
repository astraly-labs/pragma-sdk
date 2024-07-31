#!/bin/bash

docker run --name redis-merkle-maker -d -p 6379:6379 redis/redis-stack:latest

if [ $? -eq 0 ]; then
    echo "Redis container started successfully"
else
    echo "Failed to start Redis container"
fi
