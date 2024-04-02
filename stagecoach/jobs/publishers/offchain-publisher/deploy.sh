#!/bin/bash
aws s3 cp {{S3_SECRET_PATH}} /root/{{SERVICE_NAME}}
# Authenticate Docker to your Amazon ECR
aws ecr get-login-password --region {{region}} | docker login --username AWS --password-stdin {{aws_account_id}}.dkr.ecr.{{region}}.amazonaws.com

# Pull the latest image
docker pull {{docker_image_tag}}

# Stop the currently running container
docker stop {{SERVICE_NAME}}|| true

# Remove the stopped container
docker rm {{SERVICE_NAME}}|| true

# Run the new container
docker run --rm --name my-cron-job-container -d --log-driver=awslogs --log-opt awslogs-region={{region}} --log-opt awslogs-group={{aws_logs_group}} --env-file /root/env.list {{docker_image_tag}}
