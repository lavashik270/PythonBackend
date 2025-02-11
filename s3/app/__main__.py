from s3.app.core.loader import app
from s3.app.routers.chunk_upload import router as chunk_upload_router
from s3.app.routers.file_upload import router as chunk_upload_router

app.include_router(chunk_upload_router)

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
