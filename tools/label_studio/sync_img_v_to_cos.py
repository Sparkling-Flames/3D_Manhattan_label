import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import boto3
from botocore.client import Config


def iter_image_files(source_dir: Path):
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        for file_path in source_dir.rglob(ext):
            if file_path.is_file():
                yield file_path


def list_existing_keys(s3, bucket: str, prefix: str):
    keys = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix.rstrip("/") + "/"):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])
    return keys


def main():
    parser = argparse.ArgumentParser(description="Sync img_v to COS with verification and retries")
    parser.add_argument("--source-dir", default="data/mp3d_layout/img_v")
    parser.add_argument("--key-prefix", default="data/mp3d_layout/img_v")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="ap-guangzhou")
    parser.add_argument("--manifest-path", default="analysis_results/cos_sync_manifest_latest.json")
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()

    access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("TENCENT_SECRET_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("TENCENT_SECRET_KEY")
    if not access_key or not secret_key:
        raise RuntimeError("Missing credentials: AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or TENCENT_SECRET_ID/TENCENT_SECRET_KEY")

    endpoint_url = f"https://cos.{args.region}.myqcloud.com"
    public_base_url = f"https://{args.bucket}.cos.{args.region}.myqcloud.com"

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=args.region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"Source dir not found: {source_dir}")

    files = sorted(iter_image_files(source_dir))
    if not files:
        raise RuntimeError(f"No images found in {source_dir}")

    items = []
    for file_path in files:
        rel = file_path.relative_to(source_dir).as_posix()
        key = f"{args.key_prefix.strip('/')}/{rel}"
        items.append({
            "local_path": str(file_path.as_posix()),
            "object_key": key,
            "url": f"{public_base_url}/{key}",
            "uploaded": False,
        })

    print(f"Total local files: {len(items)}", flush=True)
    existing = list_existing_keys(s3, args.bucket, args.key_prefix)
    print(f"Existing COS keys under prefix: {len(existing)}", flush=True)

    to_upload = [item for item in items if item["object_key"] not in existing]
    print(f"Need upload: {len(to_upload)}", flush=True)

    failed = []
    total = len(to_upload)
    for idx, item in enumerate(to_upload, start=1):
        if idx == 1 or idx % 20 == 0 or idx == total:
            print(f"Upload progress: {idx}/{total}", flush=True)

        ok = False
        for attempt in range(1, args.max_retries + 1):
            try:
                with open(item["local_path"], "rb") as f:
                    body = f.read()
                local_lower = item["local_path"].lower()
                if local_lower.endswith((".jpg", ".jpeg")):
                    content_type = "image/jpeg"
                elif local_lower.endswith(".webp"):
                    content_type = "image/webp"
                else:
                    content_type = "image/png"

                s3.put_object(
                    Bucket=args.bucket,
                    Key=item["object_key"],
                    Body=body,
                    ACL="public-read",
                    ContentType=content_type,
                )
                ok = True
                break
            except Exception as exc:
                if attempt < args.max_retries:
                    print(f"Retry {attempt}/{args.max_retries} for {item['object_key']}", flush=True)
                if attempt == args.max_retries:
                    failed.append({"item": item, "error": repr(exc)})

        item["uploaded"] = ok

    if failed:
        print(f"Failed uploads: {len(failed)}", flush=True)
        for entry in failed[:10]:
            print(f"FAILED {entry['item']['object_key']} :: {entry['error']}", flush=True)
    else:
        print("All uploads succeeded.", flush=True)

    final_existing = list_existing_keys(s3, args.bucket, args.key_prefix)
    matched = sum(1 for item in items if item["object_key"] in final_existing)
    print(f"Remote matched count: {matched}/{len(items)}", flush=True)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(source_dir.as_posix()),
        "bucket": args.bucket,
        "region": args.region,
        "endpoint_url": endpoint_url,
        "public_base_url": public_base_url,
        "total_local": len(items),
        "existing_before": len(existing),
        "uploaded_attempted": len(to_upload),
        "failed_count": len(failed),
        "remote_matched_count": matched,
        "items": items,
        "failed": failed,
    }

    manifest_path = Path(args.manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Manifest written: {manifest_path}", flush=True)

    if failed or matched != len(items):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
