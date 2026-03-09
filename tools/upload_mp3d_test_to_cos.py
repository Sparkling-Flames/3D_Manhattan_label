"""
批量上传 MP3D test 图片到腾讯云 COS（S3 兼容接口）。

说明（中文）：
1) 上传到 COS 的是“图片文件”（png/jpg/webp），不是 Label Studio 的导入 JSON。
2) Label Studio 导入 JSON 由 `tools/prepare_labelstudio_docker.py` 生成，
    并在 Label Studio 页面中导入（JSON 不需要上传到 COS）。
3) 为了兼容你当前数据组织，本脚本默认保持对象命名：
    `data/mp3d_layout/test/img/<原文件名>`。
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime


def iter_image_files(source_dir: Path):
    """递归扫描图片文件。"""
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        for file_path in source_dir.rglob(ext):
            if file_path.is_file():
                yield file_path


def build_public_url(public_base_url: str, object_key: str) -> str:
    """拼接对象公开访问 URL。"""
    return f"{public_base_url.rstrip('/')}/{object_key.lstrip('/')}"


def main():
    parser = argparse.ArgumentParser(description="批量上传 MP3D test 图片到腾讯云 COS（S3 兼容）。")
    parser.add_argument("--source-dir", default="data/mp3d_layout/test/img", help="本地图片目录。")
    parser.add_argument("--key-prefix", default="data/mp3d_layout/test/img", help="COS 对象 key 前缀。")
    parser.add_argument("--bucket", required=True, help="COS 存储桶名称，例如 label-images-1389474327")
    parser.add_argument("--region", default="ap-guangzhou", help="COS 地域，例如 ap-guangzhou")
    parser.add_argument("--endpoint-url", default="", help="可选 S3 endpoint，默认 https://cos.<region>.myqcloud.com")
    parser.add_argument("--public-base-url", default="", help="可选公开 URL 前缀，默认 https://<bucket>.cos.<region>.myqcloud.com")
    parser.add_argument("--manifest-path", default="analysis_results/cos_upload_manifest_latest.json", help="上传清单输出路径。")
    parser.add_argument("--dry-run", action="store_true", help="仅演练，不实际上传。")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"Source dir not found: {source_dir}")

    endpoint_url = args.endpoint_url or f"https://cos.{args.region}.myqcloud.com"
    public_base_url = args.public_base_url or f"https://{args.bucket}.cos.{args.region}.myqcloud.com"

    image_files = sorted(iter_image_files(source_dir))
    if not image_files:
        raise RuntimeError(f"No images found in {source_dir}")

    planned = []
    for file_path in image_files:
        rel = file_path.relative_to(source_dir).as_posix()
        object_key = f"{args.key_prefix.strip('/')}/{rel}"
        planned.append(
            {
                "local_path": str(file_path.as_posix()),
                "object_key": object_key,
                "title": file_path.name,
                "url": build_public_url(public_base_url, object_key),
            }
        )

    if not args.dry_run:
        access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("TENCENT_SECRET_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("TENCENT_SECRET_KEY")
        if not access_key or not secret_key:
            raise RuntimeError(
                "缺少凭证：请设置 AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY 或 TENCENT_SECRET_ID/TENCENT_SECRET_KEY。"
            )

        import boto3
        from botocore.client import Config

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=args.region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

        total = len(planned)
        print(f"开始上传，共 {total} 个文件...", flush=True)
        for idx, item in enumerate(planned, start=1):
            if idx == 1 or idx % 20 == 0 or idx == total:
                print(f"上传进度: {idx}/{total}", flush=True)
            try:
                s3.upload_file(
                    Filename=item["local_path"],
                    Bucket=args.bucket,
                    Key=item["object_key"],
                    ExtraArgs={"ACL": "public-read"},
                )
            except Exception as e:
                raise RuntimeError(f"上传失败: key={item['object_key']} local={item['local_path']}") from e

    manifest_path = Path(args.manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(source_dir.as_posix()),
        "bucket": args.bucket,
        "region": args.region,
        "endpoint_url": endpoint_url,
        "public_base_url": public_base_url,
        "count": len(planned),
        "items": planned,
    }

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"已处理文件数量: {len(planned)}")
    print(f"上传清单已写入: {manifest_path}")
    if args.dry_run:
        print("当前为 dry-run，未执行实际上传。")


if __name__ == "__main__":
    main()
