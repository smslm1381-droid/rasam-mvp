"""ورودی ASGI مخصوص Cloudflare؛ uvicorn در Worker لازم نیست."""

from workers import asgi
from gateway.app import app

Default = asgi.entrypoint(app)
