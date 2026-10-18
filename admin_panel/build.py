"""بستهٔ صریح پنل فقط کد لازم دارد؛ فایل محیط و اطلاعات مدیر بسته‌بندی نمی‌شوند."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FILES = ("__init__.py", "app.py", "auth.py", "store.py", "mutations.py", "operations.py", "http.py")


def build():
    target = ROOT / "admin_panel/.worker"
    shared = ["gateway/__init__.py", "gateway/licenses.py", "gateway/license_commands.py"]
    expected = {"worker.py", *shared}
    expected.update("admin_panel/" + name for name in FILES)
    if target.exists() and any(path.is_file() and path.relative_to(target).as_posix() not in expected for path in target.rglob("*")):
        raise ValueError("فایل ناشناخته در بستهٔ پنل وجود دارد؛ ساخت متوقف شد.")
    for name in ["worker.py", *("admin_panel/" + name for name in FILES), *shared]:
        source = ROOT / ("admin_panel/worker.py" if name == "worker.py" else name)
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_bytes() != source.read_bytes():
            shutil.copyfile(source, destination)
    fonts = ROOT / "admin_panel/public/fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    for name in ["Vazirmatn-33.003.woff2", "OFL.txt", "README.txt"]:
        shutil.copyfile(ROOT / "website/public/fonts" / name, fonts / name)
    return target


if __name__ == "__main__":
    build()
