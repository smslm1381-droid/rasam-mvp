"""خطاهای قابل نمایش فقط متن کنترل‌شده دارند؛ پیام خام پایگاه یا شبکه برنمی‌گردد."""


class PortalError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status
