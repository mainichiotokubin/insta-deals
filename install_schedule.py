"""
Mac の launchd に定期実行を登録する
  - 毎朝7:00 に下書き作成（通知が来る）
  - settings.json の publish_times に承認済みの下書きを1件ずつ投稿
  - 確認画面 http://127.0.0.1:8765 を常時起動

登録:   .venv/bin/python install_schedule.py
解除:   .venv/bin/python install_schedule.py --uninstall
"""
import plistlib
import subprocess
import sys
from pathlib import Path

from deals.config import ROOT, env, settings

AGENTS = Path.home() / "Library/LaunchAgents"
PY = str(ROOT / ".venv/bin/python")
LOGS = ROOT / "data/logs"


def job(label, args, **extra):
    return label, {
        "Label": label,
        "ProgramArguments": [PY, str(ROOT / "cli.py"), *args],
        "WorkingDirectory": str(ROOT),
        "StandardOutPath": str(LOGS / f"{label}.log"),
        "StandardErrorPath": str(LOGS / f"{label}.log"),
        **extra,
    }


def jobs():
    times = []
    for t in settings()["publish_times"]:
        h, m = t.split(":")
        times.append({"Hour": int(h), "Minute": int(m)})
    out = [
        job("com.insta-deals.draft", ["draft"], StartCalendarInterval={"Hour": 7, "Minute": 0}),
        job("com.insta-deals.review", ["review"], RunAtLoad=True, KeepAlive=True),
    ]
    # Instagram API が使えるときだけ自動投稿を登録（それまでは手動投稿モード）
    if env("IG_ACCESS_TOKEN", required=False):
        out.append(job("com.insta-deals.publish", ["publish"], StartCalendarInterval=times))
    return out


def main():
    uninstall = "--uninstall" in sys.argv
    LOGS.mkdir(parents=True, exist_ok=True)
    for label, plist in jobs():
        path = AGENTS / f"{label}.plist"
        if path.exists():
            subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
        if uninstall:
            path.unlink(missing_ok=True)
            print(f"解除: {label}")
            continue
        AGENTS.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        subprocess.run(["launchctl", "load", str(path)], check=True)
        print(f"登録: {label}")


if __name__ == "__main__":
    main()
