import asyncio

import boto3
from botocore.config import Config


class Storage:
  def __init__(self, settings):
    self.settings = settings
    self.client = boto3.client(
      "s3", endpoint_url=settings.s3_endpoint_url, region_name=settings.s3_region,
      aws_access_key_id=settings.s3_access_key_id.get_secret_value() or "not-configured",
      aws_secret_access_key=settings.s3_secret_access_key.get_secret_value() or "not-configured",
      config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                    connect_timeout=5, read_timeout=20, retries={"max_attempts": 2}),
    )

  async def upload_url(self, row):
    # POST policy enforces object size, MIME type, hash metadata, and server-generated key.
    return await asyncio.to_thread(
      self.client.generate_presigned_post, Bucket=row["bucket"], Key=row["object_key"],
      Fields={"Content-Type": row["mime_type"], "x-amz-meta-sha256": row["sha256"]},
      Conditions=[{"Content-Type": row["mime_type"]}, {"x-amz-meta-sha256": row["sha256"]},
                  ["content-length-range", row["size_bytes"], row["size_bytes"]]], ExpiresIn=300,
    )

  async def head(self, row):
    return await asyncio.to_thread(self.client.head_object, Bucket=row["bucket"], Key=row["object_key"])

  async def read(self, row):
    def read():
      kwargs = {"Bucket": row["bucket"], "Key": row["object_key"]}
      if row["metadata"].get("version_id"):
        kwargs["VersionId"] = row["metadata"]["version_id"]
      response = self.client.get_object(**kwargs)
      with response["Body"] as body:
        data = body.read(self.settings.max_upload_bytes + 1)
      if len(data) != row["size_bytes"] or len(data) > self.settings.max_upload_bytes:
        raise ValueError("file_size_mismatch")
      return data
    return await asyncio.to_thread(read)

  async def download_url(self, row):
    params = {"Bucket": row["bucket"], "Key": row["object_key"]}
    if row["metadata"].get("version_id"):
      params["VersionId"] = row["metadata"]["version_id"]
    return await asyncio.to_thread(self.client.generate_presigned_url,
      "get_object", Params=params, ExpiresIn=120)
