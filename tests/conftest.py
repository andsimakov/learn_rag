import os

# Stub env vars so Settings() can be instantiated without a real .env.
# app/main.py calls load_dotenv() at import time, but test files import from
# app.services / app.api directly, bypassing main.py — so .env is never loaded
# during tests. These stubs are the only values available in the test environment.
_STUBS = {
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "ANTHROPIC_API_KEY": "test",
    "LANGFUSE_PUBLIC_KEY": "test",
    "LANGFUSE_SECRET_KEY": "test",
}

for key, value in _STUBS.items():
    os.environ.setdefault(key, value)
