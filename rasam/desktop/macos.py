"""مک کلیک دوباره روی Dock را به فرایند موجود می‌فرستد؛ سرور دوم اجرا نمی‌شود."""

import threading

import AppKit
import httpx
import objc
from PyObjCTools import AppHelper

from rasam import config
from rasam.desktop.instance import DesktopInstance
from rasam.desktop.browser import open_page


class ApplicationDelegate(AppKit.NSObject):
    def applicationDidFinishLaunching_(self, notification):
        threading.Thread(target=self.runServer, daemon=True).start()

    @objc.python_method
    def runServer(self):
        try:
            self.result = self.serve()
        except Exception:
            self.result = 1
        finally:
            self.finished = True
            AppHelper.callAfter(self.application.terminate_, None)

    def applicationShouldHandleReopen_hasVisibleWindows_(self, application, visible):
        url = DesktopInstance(config.DATA_HOME).read_url()
        if url:
            open_page(url)
        return False

    def applicationShouldTerminate_(self, application):
        if self.finished:
            return AppKit.NSTerminateNow
        url = DesktopInstance(config.DATA_HOME).read_url()
        if url:
            from urllib.parse import urlsplit, parse_qs
            parts = urlsplit(url)
            token = parse_qs(parts.query)["token"][0]
            try:
                httpx.post(f"{parts.scheme}://{parts.netloc}/shutdown",
                           headers={"X-Rasam-Token": token}, trust_env=False, timeout=2)
            except httpx.HTTPError:
                pass
        # خروج عادی سرور قفل و سوکت را آزاد می‌کند و سپس حلقهٔ مک را می‌بندد.
        return AppKit.NSTerminateCancel


def run(serve):
    application = AppKit.NSApplication.sharedApplication()
    application.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    delegate = ApplicationDelegate.alloc().init()
    delegate.application = application
    delegate.serve = serve
    delegate.finished = False
    delegate.result = 0
    application.setDelegate_(delegate)
    application.run()
    return delegate.result
