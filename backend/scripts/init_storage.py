"""Create a private, versioned S3-compatible bucket. Explicit administrative command."""
from botocore.exceptions import ClientError

from app.config import get_settings
from app.services.storage import Storage


def main():
  settings = get_settings()
  client = Storage(settings).client
  try:
    client.head_bucket(Bucket=settings.s3_bucket)
  except ClientError as error:
    if error.response["Error"]["Code"] not in {"404", "NoSuchBucket", "NotFound"}:
      raise
    options = {"Bucket": settings.s3_bucket}
    if settings.s3_region != "us-east-1":
      options["CreateBucketConfiguration"] = {"LocationConstraint": settings.s3_region}
    client.create_bucket(**options)
  client.put_bucket_versioning(Bucket=settings.s3_bucket, VersioningConfiguration={"Status": "Enabled"})
  try:
    client.put_bucket_cors(Bucket=settings.s3_bucket, CORSConfiguration={"CORSRules": [{
    "AllowedOrigins": settings.cors_origins,
    "AllowedMethods": ["POST", "GET", "HEAD"], "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag", "x-amz-version-id"], "MaxAgeSeconds": 300,
    }]})
  except ClientError as error:
    if error.response["Error"]["Code"] != "NotImplemented":
      raise
    print("该 S3 实现使用服务级 CORS；本地 Compose 已通过 MINIO_API_CORS_ALLOW_ORIGIN 配置。")
  print("私有存储桶已就绪，已启用版本控制；未设置公开策略。")


if __name__ == "__main__":
  main()
