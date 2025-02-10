from fastapi import APIRouter, UploadFile, Form, Request, HTTPExeption, File  # noqa

router = APIRouter(prefix="/upload/file")


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    try:
    except:
        ...
