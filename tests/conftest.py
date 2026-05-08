import os

# Stub env vars so Settings() can be instantiated in tests without a real .env.
# setdefault means a real .env (loaded by app/main.py) takes precedence.
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
