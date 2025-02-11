from fastapi import APIRouter, UploadFile, Form, Request, HTTPExeption, File  # noqa

from s3.app.core.config import settings
from s3.app.utils.s3 import s3_client

router = APIRouter(prefix="/upload/file")


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_bytes = file.read()
        s3_key = f"example/{file.filename}"  # Replace the example with your real path
        await s3_client.upload_file_multipart(settings.S3_BUCKET, s3_key, file_bytes=file_bytes)
    except:
        raise HTTPExeption(status_code=500, detail="S3 upload failed")
