"""Child process entry point; never calls an external model or device."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path


def deny_network(event: str, args: tuple) -> None:
    if event in {"socket.connect", "socket.bind"} and args[0].family in {
        socket.AF_INET,
        socket.AF_INET6,
    }:
        raise RuntimeError("Network disabled by executor spike")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backend", choices=["raw-inspect", "native", "inspect"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--retry")
    parser.add_argument("--judge")
    args = parser.parse_args()
    sys.addaudithook(deny_network)
    if args.judge:
        from .engine import judge
        from .store import Store

        store = Store(args.root)
        attempt = store.sample(args.judge)["selected"]
        observed = next(r for r in store.rows("observations") if r["attempt"] == attempt)
        result = judge(store, args.judge, json.loads(observed["payload"]), {"supported": True})
        print(json.dumps(result), flush=True)
        return
    if args.backend == "native":
        from .engine import run

        run(args.root, "native")
        return

    from inspect_ai import eval, eval_retry

    from .inspect_tasks import raw_probe

    if args.backend == "inspect":
        from .engine import run

        run(args.root, "inspect")
        return

    options = dict(
        display="none",
        log_dir=str(args.root / "inspect-logs"),
        max_samples=1,
        log_buffer=1,
        log_realtime=False,
        score=False,
        ctl_server=False,
        acp_server=False,
    )
    if args.retry:
        logs = eval_retry(args.retry, **options)
    else:
        logs = eval(raw_probe(str(args.root)), model="mockllm/model", **options)
    print(json.dumps({"logs": [log.location for log in logs]}), flush=True)


if __name__ == "__main__":
    main()
