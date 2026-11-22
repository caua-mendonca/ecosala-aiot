"""Heartbeat simples para o healthcheck dos serviços sem HTTP.

O serviço chama beat() no seu laço principal; o Docker roda
`python -m ecosala_common.health 60`, que falha se o último beat tiver mais
de 60 segundos.
"""
from __future__ import annotations

import os
import sys
import time

PATH = os.getenv("HEARTBEAT_FILE", "/tmp/heartbeat")
_last = 0.0


def beat() -> None:
    global _last
    now = time.time()
    if now - _last >= 5:
        _last = now
        try:
            with open(PATH, "w") as fh:
                fh.write(str(now))
        except OSError:
            pass


def main() -> int:
    max_age = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    try:
        with open(PATH) as fh:
            age = time.time() - float(fh.read().strip())
    except (OSError, ValueError):
        return 1
    return 0 if age <= max_age else 1


if __name__ == "__main__":
    sys.exit(main())
