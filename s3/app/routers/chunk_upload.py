import os
import shutil
import uuid

import aiofiles
from fastapi import APIRouter, UploadFile, Form, Request, HTTPExeption  # noqa
from loguru import logger  # noqa

from s3.app.core.config import UPLOAD_DIR, settings
from s3.app.utils.s3 import s3_client

router = APIRouter(prefix="/upload/chunk")


@router.post("/init")
async def init_upload_handler(
        filename: str = Form(...),
        file_size: int = Form(...),
) -> dict:
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOAD_DIR, upload_id)
    os.makedirs(upload_dir, exist_ok=True)

    return {"upload_id": upload_id}


@router.post("/")
async def upload_chunk_handler(
        upload_id: str = Form(...),
        chunk_index: int = Form(...),
        file: UploadFile = Form(...),
) -> dict:
    try:
        upload_dir = os.path.join(UPLOAD_DIR, upload_id)
        if not os.path.exists(upload_dir):
            logger.warning(f"Invalid upload id: {upload_id}")
            return HTTPExeption(status_code=403, detail="Invalid upload id")
        chunk_filename = os.path.join(upload_dir, f"chunk_{chunk_index}")
        async with aiofiles.open(chunk_filename, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                await f.write(chunk)
        return {"detail": "chunk uploaded"}
    except Exception as e:
        logger.error(f"Error uploading chunk: {e}")
        return HTTPExeption(status_code=403, detail="Error uploading chunk")


@router.post("/complete")
async def complete_upload_handler(
        upload_id: str = Form(...),
        filename: str = Form(...),
):
    upload_dir = os.path.join(UPLOAD_DIR, upload_id)
    if not os.path.exists(upload_dir):
        logger.error(f"Invalid upload id: {upload_id}")
        return HTTPExeption(status_code=403, content="Invalid upload id")

    chunk_files = sorted(
        [f for f in os.listdir(upload_dir) if f.startswith("chunk_")],
        key=lambda x: int(x.split("_")[1])
    )

    merged_filepath = os.path.join(UPLOAD_DIR, f"{upload_id}_{filename}")
    with open(merged_filepath, "wb") as merged_file:
        for chunk_file in chunk_files:
            chunk_path = os.path.join(upload_dir, chunk_file)
            with open(chunk_path, "rb") as cf:
                while True:
                    data = cf.read(1024 * 1024)
                    if not data:
                        break
                    merged_file.write(data)

    shutil.rmtree(upload_dir)
    s3_key = f"{settings.S3_KEY}/{filename}"

    try:
        await s3_client.upload_file_multipart(settings.S3_BUCKET, s3_key, merged_filepath)
    except Exception as e:
        logger.error(f"Error uploading merged file to S3: {e}")
        return HTTPExeption(status_code=500, detail="Error uploading merged file to S3")

    os.remove(merged_filepath)

    return {"detail": "Successful Upload Video"}
