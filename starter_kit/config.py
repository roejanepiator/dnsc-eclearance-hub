"""Central config for the e-Clearance Hub. Loads .env via python-dotenv.

    from config import REGISTRAR_API_KEY, HMAC_SIGNING_KEY
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env next to this file so it works no matter where you run from.
# override=False: real environment variables (e.g. on a server) win over .env.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)


def need(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable {name}. Check your .env file.")
    return value


REGISTRAR_API_KEY = need("REGISTRAR_API_KEY")
HMAC_SIGNING_KEY = need("HMAC_SIGNING_KEY")
APP_SECRET_KEY = need("APP_SECRET_KEY")
STARTER_HMAC_KEY = need("STARTER_HMAC_KEY")
REGISTRAR_BASE_URL = os.environ.get("REGISTRAR_BASE_URL", "http://127.0.0.1:8001/api/v1")
