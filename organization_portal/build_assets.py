"""فقط دارایی عمومی برند و کتابخانهٔ نمودار کپی می‌شوند؛ داده یا تنظیمات وارد سایت نمی‌شوند."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent


def build():
    destination = ROOT / "organization_portal/public/static"
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "mark.svg": ROOT / "assets/brand/mark.svg",
        "Vazirmatn.woff2": ROOT / "website/public/fonts/Vazirmatn-33.003.woff2",
        "plotly.min.js": ROOT / "rasam/desktop/static/plotly.min.js",
        "PLOTLY-LICENSE.txt": ROOT / "rasam/desktop/static/PLOTLY-LICENSE.txt",
        "FONT-LICENSE.txt": ROOT / "website/public/fonts/OFL.txt",
    }
    for name, source in files.items():
        shutil.copyfile(source, destination / name)
    return destination


if __name__ == "__main__":
    build()
