"""半自動モード：画像とキャプションを iPhone に渡す（写真アプリ・メモ・iCloud Drive）"""
import shutil
import subprocess
from pathlib import Path

from .config import DRAFTS, settings

ICLOUD = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs"


def _osascript(script, timeout=90):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])


def _as_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_icloud_drive(draft, folder_name):
    dest = ICLOUD / folder_name / draft["id"]
    dest.mkdir(parents=True, exist_ok=True)
    for name in draft["images"]:
        shutil.copy(DRAFTS / draft["id"] / name, dest / name)
    (dest / "caption.txt").write_text(draft["caption"], encoding="utf-8")
    return dest


def to_photos(draft, album):
    files = ", ".join(f'POSIX file {_as_str(str(DRAFTS / draft["id"] / n))}' for n in draft["images"])
    _osascript(f'''
tell application "Photos"
    if not (exists album {_as_str(album)}) then make new album named {_as_str(album)}
    import {{{files}}} into album {_as_str(album)} skip check duplicates true
end tell''')


def to_notes(draft, folder):
    import html
    body = "<br>".join(html.escape(line) for line in draft["caption"].split("\n"))
    title = html.escape(f"{draft['date_label']} キャプション")
    _osascript(f'''
tell application "Notes"
    if not (exists folder {_as_str(folder)}) then make new folder with properties {{name:{_as_str(folder)}}}
    make new note at folder {_as_str(folder)} with properties {{body:{_as_str(f"<h1>{title}</h1>" + body)}}}
end tell''')


def export_for_phone(draft):
    """できた方法を返す。どれか1つでも成功すればOK"""
    name = settings()["account_name"]
    done, errors = [], []
    for label, fn in (("iCloud Drive", lambda: to_icloud_drive(draft, name)),
                      ("写真アプリ", lambda: to_photos(draft, name)),
                      ("メモアプリ", lambda: to_notes(draft, name))):
        try:
            fn()
            done.append(label)
        except Exception as e:
            errors.append(f"{label}: {e}")
    return done, errors
