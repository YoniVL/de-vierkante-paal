"""Bootstrap voor de Android-app (Chaquopy).

MainActivity roept ``start(data_dir)`` aan. We zetten eerst DVP_DATA_DIR
(zodat de tool naar een schrijfbare map schrijft i.p.v. de read-only
Python-bronmap), starten dan de gewone ``dvp.app``-server in een thread en
geven de poort terug.
"""

from __future__ import annotations

import os
import threading


def start(data_dir: str) -> int:
    os.environ.setdefault("DVP_DATA_DIR", data_dir)
    os.environ.setdefault("DVP_HARTSLAG_TIMEOUT", "999999")  # niet auto-afsluiten

    from dvp import config
    from dvp.app import main

    threading.Thread(
        target=lambda: main(open_browser=False),
        name="dvp-server",
        daemon=True,
    ).start()
    return int(config.PORT)
