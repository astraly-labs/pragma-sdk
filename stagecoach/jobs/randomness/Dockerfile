FROM amazon/aws-lambda-python:3.11

RUN yum install -y gcc python-devel gmp-devel git
RUN python -m pip install --upgrade pip
RUN pip install pragma-sdk

COPY app.py ${LAMBDA_TASK_ROOT}

CMD [ "app.handler" ] 