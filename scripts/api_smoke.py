from __future__ import annotations

import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

API_URL = os.getenv("API_URL", "http://localhost:8000")

SAMPLE = {
    "company_name": "Melatee",
    "website": "melatee.com",
    "phone_number": "+1 (823) 850-3803",
    "facebook_url": "facebook.com/melatee",
}

def http_get(path: str):
    url = f"{API_URL}{path}"
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=5) as resp:
            data = resp.read()
            return resp.getcode(), data
    except HTTPError as e:
        return e.code, e.read()
    except URLError as e:
        raise e


def http_post(path: str, body: dict):
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            data = resp.read()
            return resp.getcode(), data
    except HTTPError as e:
        return e.code, e.read()
    except URLError as e:
        raise SystemExit(f"[API-SMOKE] POST {url} failed: {e}")


def main():
    print("[API-SMOKE] API_URL:", API_URL)

    # 1) Health check
    # Try a few times in case server is just starting
    attempts = 10
    delay = 0.5
    while True:
        try:
            status, data = http_get("/healthz")
            break
        except URLError as e:
            attempts -= 1
            if attempts <= 0:
                raise SystemExit(f"[API-SMOKE] GET /healthz failed after retries: {e}")
            time.sleep(delay)
    print("[API-SMOKE] /healthz:", status, data.decode("utf-8", errors="ignore"))
    if status != 200:
        raise SystemExit(1)

    # 2) Match request
    status, data = http_post("/match", SAMPLE)
    print("[API-SMOKE] /match:", status)
    try:
        obj = json.loads(data.decode("utf-8", errors="ignore"))
        print(json.dumps(obj, indent=2))
    except Exception:
        print(data.decode("utf-8", errors="ignore"))

    if status not in (200, 201):
        raise SystemExit(1)

    print("[API-SMOKE] OK")


if __name__ == "__main__":
    main()
