#!/usr/bin/env python3
"""
Entry point for: python -m tsv6_pisignage

Standalone launcher for the PiSignageKiosk.
On a production Pi, this is typically started by production_main.py
which injects the AWS manager, servo controller, etc.

This standalone mode is useful for testing the overlay + piSignage
integration without TSV6 hardware dependencies.
"""

import logging
import os

from .kiosk import PiSignageKiosk


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    server_url = os.getenv("PISIGNAGE_SERVER_URL", "")
    user = os.getenv("PISIGNAGE_USER", "")
    password = os.getenv("PISIGNAGE_PASSWORD", "")
    event_images = os.getenv("EVENT_IMAGES_DIR", "event_images")

    kiosk = PiSignageKiosk(
        pisignage_server_url=server_url,
        pisignage_user=user,
        pisignage_password=password,
        event_images_dir=event_images,
    )

    kiosk.setup()
    kiosk.run()


main()
