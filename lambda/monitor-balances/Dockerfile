FROM public.ecr.aws/lambda/python:3.11

RUN pip install pragma-sdk

# Install additional dependencies
RUN pip install \
    boto3 \
    requests \
    python-telegram-bot==20.8

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["app.handler"]
