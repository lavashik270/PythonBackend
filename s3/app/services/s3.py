from typing import Any

import aiohttp
import aiofiles
import hashlib
import hmac
import datetime
import json
import base64
import os


class S3ClientException(Exception):
    """ Custom exception for S3 operations. """

    def __init__(self, status_code: int, message: Any) -> None:
        self.status_code = status_code
        self.message = message

    def __str__(self) -> str:
        return f"S3 Client Error with status code {self.status_code}: {self.message}"


class S3Client:
    """ S3 client used instead of boto3 to avoid errors with signing file bytes. """

    def __init__(self, access_key: str, secret_key: str, endpoint: str, region: str = "us-east-1"):
        """ Initialize the S3Client with AWS credentials, endpoint, and region. """
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = endpoint
        self.region = region

    @staticmethod
    def get_signature_key(key: str, date_stamp: str, region: str, service: str) -> bytes:
        """ Generate the AWS Signature Version 4 signing key using the secret key, date stamp, region, and service. """
        k_date = hmac.new(("AWS4" + key).encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service.encode("utf-8"), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        return k_signing

    def sign_request(self, method: str, bucket: str, key: str, headers: dict, payload_hash: str) -> dict:
        """ Sign the HTTP request for S3 using AWS Signature Version 4 by constructing the canonical request, creating the string to sign, and appending the required authorization headers. """
        service = "s3"
        algorithm = "AWS4-HMAC-SHA256"
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        canonical_uri = f"/{key}"
        canonical_headers = (
            f"host:{bucket}.{self.endpoint}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = f"{method}\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        signing_key = self.get_signature_key(self.secret_key, date_stamp, self.region, service)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{algorithm} Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers["Authorization"] = authorization_header
        headers["x-amz-date"] = amz_date
        headers["x-amz-content-sha256"] = payload_hash

        return headers

    async def upload_file(self, bucket: str, key: str, file_path: str = None, file_bytes: bytes = None) -> None:
        """ Asynchronously upload a file to the specified S3 bucket using the HTTP PUT method. """
        if file_path:
            async with aiofiles.open(file_path, "rb") as f:
                data = await f.read()
        else:
            data = file_bytes

        payload_hash = hashlib.sha256(data).hexdigest()
        headers = self.sign_request("PUT", bucket, key, {}, payload_hash)
        url = f"https://{bucket}.{self.endpoint}/{key}"

        async with aiohttp.ClientSession() as session:
            async with session.put(url, data=data, headers=headers) as response:
                if response.status not in (200, 204):
                    text = await response.text()
                    raise S3ClientException(status_code=response.status, message=text)

    async def upload_file_multipart(self, bucket: str, key: str, file_path: str) -> None:
        """ Asynchronously upload a file to the specified S3 bucket using the HTTP POST method with multipart/form-data. This method utilizes an S3 POST policy with AWS Signature Version 4. """
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        service = "s3"
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        credential = f"{self.access_key}/{credential_scope}"

        expiration = (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        policy_document = {
            "expiration": expiration,
            "conditions": [
                {"bucket": bucket},
                {"key": key},
                {"x-amz-algorithm": algorithm},
                {"x-amz-credential": credential},
                {"x-amz-date": amz_date}
            ]
        }

        policy_json = json.dumps(policy_document)
        policy_base64 = base64.b64encode(policy_json.encode("utf-8")).decode("utf-8")

        signing_key = self.get_signature_key(self.secret_key, date_stamp, self.region, service)
        signature = hmac.new(signing_key, policy_base64.encode("utf-8"), hashlib.sha256).hexdigest()

        async with aiofiles.open(file_path, "rb") as f:
            file_data = await f.read()

        form = aiohttp.FormData()
        form.add_field("key", key)
        form.add_field("x-amz-algorithm", algorithm)
        form.add_field("x-amz-credential", credential)
        form.add_field("x-amz-date", amz_date)
        form.add_field("policy", policy_base64)
        form.add_field("x-amz-signature", signature)
        form.add_field(
            "file",
            file_data,
            filename=os.path.basename(file_path),
            content_type="application/octet-stream"
        )

        url = f"https://{bucket}.{self.endpoint}/"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form) as response:
                if response.status not in (200, 204):
                    text = await response.text()
                    raise S3ClientException(status_code=response.status, message=text)
