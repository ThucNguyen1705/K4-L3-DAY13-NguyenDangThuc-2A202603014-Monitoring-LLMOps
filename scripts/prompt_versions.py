"""Quản lý prompt day13-chat trên project Langfuse cá nhân (đọc key từ .env).

    python scripts/prompt_versions.py status              # label nào đang trỏ version nào
    python scripts/prompt_versions.py bootstrap           # tạo v1 (baseline, production) và v2 (candidate)
    python scripts/prompt_versions.py promote --version 2 # chuyển production sang v2
    python scripts/prompt_versions.py promote --version 1 # rollback production về v1

Label trong Langfuse là duy nhất giữa các version: gán production cho một version sẽ tự gỡ
label đó khỏi version cũ. Sau khi đổi label, restart API để tiến trình cũ không dùng cache.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.prompt_management import DEFAULT_PROMPT_TEMPLATE

LABELS = ("baseline", "candidate", "production")
# Nhãn "vai trò" gốc của mỗi version, giữ lại khi promote để không mất baseline/candidate.
ROLE_LABEL = {1: "baseline", 2: "candidate"}
V2_TEMPLATE = "Answer in no more than three concise bullet points.\n" + DEFAULT_PROMPT_TEMPLATE


def prompt_name() -> str:
    return os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")


def label_versions(client: Any, name: str) -> dict[str, int | None]:
    versions: dict[str, int | None] = {}
    for label in LABELS:
        try:
            prompt = client.get_prompt(name, label=label, type="text", cache_ttl_seconds=0, max_retries=0)
            versions[label] = None if getattr(prompt, "is_fallback", False) else int(prompt.version)
        except Exception:  # prompt/label chưa tồn tại
            versions[label] = None
    return versions


def bootstrap(client: Any, name: str) -> list[str]:
    existing = label_versions(client, name)
    actions = []
    if existing["baseline"] is None:
        client.create_prompt(name=name, prompt=DEFAULT_PROMPT_TEMPLATE, labels=["baseline", "production"],
                             type="text", commit_message="v1 baseline")
        actions.append("created v1 with labels baseline, production")
    if existing["candidate"] is None:
        client.create_prompt(name=name, prompt=V2_TEMPLATE, labels=["candidate"], type="text",
                             commit_message="v2 candidate: concise bullet answers")
        actions.append("created v2 with label candidate")
    return actions or ["prompt already has baseline and candidate; nothing to create"]


def promote(client: Any, name: str, version: int) -> None:
    labels = [label for label in (ROLE_LABEL.get(version), "production") if label]
    client.update_prompt(name=name, version=version, new_labels=labels)


def make_client() -> Any:
    from dotenv import load_dotenv
    from langfuse import Langfuse

    load_dotenv(REPO_ROOT / ".env")
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        raise SystemExit("Thiếu LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY trong .env")
    return Langfuse()


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("bootstrap")
    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("--version", type=int, required=True)
    args = parser.parse_args()

    client = make_client()
    name = prompt_name()
    if args.command == "bootstrap":
        for action in bootstrap(client, name):
            print(action)
    elif args.command == "promote":
        before = label_versions(client, name)["production"]
        promote(client, name, args.version)
        print(f"production: v{before} -> v{args.version} (restart API trước khi chạy load test)")
    for label, version in label_versions(client, name).items():
        print(f"{name} [{label}] -> v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
