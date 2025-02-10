from s3.app.core.config import settings
from s3.app.services.s3 import S3Client

s3_client = S3Client(
    access_key=settings.S3_ACCESS_KEY,
    secret_key=settings.S3_SECRET_ACCESS_KEY,
    endpoint=settings.S3_ENDPOINT,
    region=settings.S3_REGION
)