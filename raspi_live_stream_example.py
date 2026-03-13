"""
Example Raspberry Pi client for streaming harness data to the Flask backend.

This script POSTs samples to the `/ingest` endpoint defined in `app.py`.
You can either:
 1) Import `send_samples` into your own sensor script, or
 2) Run this file directly to send dummy test data.
"""

import argparse
import time
from typing import Iterable, Mapping, Any

import requests


DEFAULT_BACKEND_URL = "http://127.0.0.1:5000/ingest"


def send_samples(
    samples: Iterable[Mapping[str, Any]],
    url: str = DEFAULT_BACKEND_URL,
    timeout: float = 2.0,
) -> None:
    """
    Send one or more samples to the backend.

    Each sample must be a mapping with at least:
      - timestamp : int (unix seconds)
      - bpm       : float
      - arrhythmia: int (0/1)
      - raw_ir    : int
      - raw_red   : int
    """
    payload = list(samples)
    if not payload:
        return

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"[raspi_live_stream_example] Failed to send samples: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send dummy harness data to the Dognosis backend for testing."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BACKEND_URL,
        help="Ingest endpoint URL (default: %(default)s)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between dummy samples (default: %(default)s)",
    )
    args = parser.parse_args()

    print(
        f"Sending dummy samples to {args.url} every {args.interval} seconds.\n"
        "Press Ctrl+C to stop.\n"
        "For real data, import send_samples(...) into your sensor script "
        "and pass actual sensor values."
    )

    bpm = 80.0
    try:
        while True:
            ts = int(time.time())
            # Simple fake waveform: bpm fluctuates slightly over time.
            bpm += 0.5
            if bpm > 100:
                bpm = 80.0

            sample = {
                "timestamp": ts,
                "bpm": bpm,
                "arrhythmia": 0,
                "raw_ir": 100000,
                "raw_red": 100000,
            }

            send_samples([sample], url=args.url)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopping dummy stream.")


if __name__ == "__main__":
    main()

