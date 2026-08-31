"""Bootstrap voor de Android-app (Chaquopy).

MainActivity roept ``start(data_dir)`` aan. We zetten eerst DVP_DATA_DIR
(schrijfbare map i.p.v. de read-only Python-bronmap), laten de HTTP-helpers
via Android's netwerklaag lopen (android_net) en starten dan de gewone
``dvp.app``-server in een thread.
"""

from __future__ import annotations

import os
import threading


def start(data_dir: str) -> int:
    os.environ.setdefault("DVP_DATA_DIR", data_dir)
    os.environ.setdefault("DVP_HARTSLAG_TIMEOUT", "999999")  # niet auto-afsluiten

    import android_net
    android_net.installeer()

    from dvp import config
    from dvp.app import main

    threading.Thread(
        target=lambda: main(open_browser=False),
        name="dvp-server",
        daemon=True,
    ).start()
    return int(config.PORT)
