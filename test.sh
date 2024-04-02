S3_BUCKET=pragma-cloudtrail-bucket
SERVICE_NAME=test
aws s3 cp stagecoach/jobs/publishers/offchain-publisher/deploy.sh s3://$S3_BUCKET/$SERVICE_NAME/
