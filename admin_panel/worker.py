"""ورودی مستقل پنل؛ کلید مدل و مسیر عمومی مشتری در این Worker وجود ندارند."""

from workers import asgi
from admin_panel.app import app

Default = asgi.entrypoint(app)
