FROM public.ecr.aws/lambda/python:3.12-x86_64

RUN pip install pragma-sdk==2.2.0

COPY app.py ${LAMBDA_TASK_ROOT}

CMD [ "app.handler" ]
