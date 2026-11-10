"""Per-launch local API authentication; never embed credentials in URLs or bundles."""
import os
import secrets

API_TOKEN=os.environ.get('VOLSTUDIO_TOKEN') or secrets.token_urlsafe(32)
TOKEN_HEADER='X-Studio-Token'


def authenticated(value):
    return bool(value) and secrets.compare_digest(value.encode('utf8'),API_TOKEN.encode('utf8'))
