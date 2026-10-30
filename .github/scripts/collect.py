"""Workflow orchestration; source collection remains in the tested CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


BRANCH = "001-acervo-cvm"
DATA_PATHS = ("reguladores", "cobertura", "catalogo")
BOT = {"GIT_AUTHOR_NAME": "github-actions[bot]", "GIT_COMMITTER_NAME": "github-actions[bot]",
       "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
       "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com"}


def git(*arguments, **kwargs):
    return subprocess.run(["git", *arguments], text=True, capture_output=True, check=True, **kwargs)


def guard_branch():
    if git("branch", "--show-current").stdout.strip() != BRANCH:
        raise ValueError("unexpected branch; refusing collection or push")


def parameters():
    category = os.environ.get("CVM_COLLECT_CATEGORY", "resolucoes")
    document = os.environ.get("CVM_COLLECT_DOCUMENT", "")
    batch = int(os.environ.get("CVM_COLLECT_BATCH", "0"))
    limit = int(os.environ.get("CVM_COLLECT_LIMIT", "10"))
    mode = os.environ.get("CVM_COLLECT_MODE", "batch")
    if category != "resolucoes" or batch < 0 or limit < 0 or mode not in ("batch", "incremental"):
        raise ValueError("invalid collection parameters")
    args = ["collect", "--category", category, "--output", ".", "--batch", str(batch),
            "--cache-dir", str(Path(os.environ["RUNNER_TEMP"]) / "cvm-cache"), "--min-interval", "5",
            "--user-agent", "NormasCVMResearch/0.5 (+https://github.com/StaffeToxic/normas-cvm; scheduled collection)"]
    if document:
        args.extend(("--document", document))
        label = "document"
    elif mode == "incremental":
        args.append("--incremental")
        label = "incremental"
    else:
        label = f"batch {batch}"
    if limit:
        args.extend(("--limit", str(limit)))
    return args, f"{category} {label}"


def result_path():
    return Path(os.environ["RUNNER_TEMP"]) / "cvm-collection-result.json"


def collect():
    guard_branch()
    args, label = parameters()
    result = subprocess.run([sys.executable, "-m", "cvm_archive.cli", *args], text=True, capture_output=True)
    log = Path(os.environ["RUNNER_TEMP"]) / "cvm-collect.log"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        return result.returncode
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    summary = json.loads(lines[-1]) if lines else {}
    if type(summary.get("changed")) is not bool:
        raise ValueError("CLI did not emit a boolean changed result")
    stamp = datetime.now(timezone.utc).date().isoformat()
    result_path().write_text(json.dumps({"summary": summary, "label": label, "date": stamp}), encoding="utf-8")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write("changed=" + str(summary["changed"]).lower() + "\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write("```json\n" + json.dumps(summary) + "\n```\n")
    return 0


def commit():
    guard_branch()
    result = json.loads(result_path().read_text(encoding="utf-8"))
    if result["summary"]["changed"] is not True:
        return 0
    paths = [name for name in DATA_PATHS if Path(name).is_dir()]
    if not paths:
        raise ValueError("no data directory exists")
    git("add", "--", *paths)
    staged = git("diff", "--cached", "--name-only").stdout.splitlines()
    if any(not name.startswith(tuple(prefix + "/" for prefix in DATA_PATHS)) for name in staged):
        raise ValueError("non-data changes are staged; refusing commit")
    if not staged:
        return 0
    environment = {**os.environ, **BOT}
    git("commit", "-m", f'data: collect {result["label"]} {result["date"]}', env=environment)
    git("push", "origin", "HEAD:001-acervo-cvm")
    return 0


def main(arguments=None):
    try:
        arguments = sys.argv[1:] if arguments is None else arguments
        if arguments == ["run"]:
            return collect()
        if arguments == ["commit"]:
            return commit()
        raise ValueError("expected run or commit")
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, file=sys.stderr)
        return exc.returncode
    except (OSError, ValueError, KeyError) as exc:
        print(f"workflow error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
