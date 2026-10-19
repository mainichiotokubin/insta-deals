import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DRAFTS = DATA / "drafts"
SITE = ROOT / "docs"  # GitHub Pages で公開するフォルダ


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def env(name, required=True):
    load_env()
    value = os.environ.get(name, "")
    if required and not value:
        raise SystemExit(f"{name} が .env に設定されていません")
    return value


def settings():
    return json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))


def set_env(name, value):
    """.env の値を書き換える（トークン更新用）"""
    env_file = ROOT / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    out, found = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == name:
            out.append(f"{name}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{name}={value}")
    env_file.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[name] = value
