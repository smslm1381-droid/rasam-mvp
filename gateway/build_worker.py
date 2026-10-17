"""فقط فایل‌های لازمِ سرور به بسته می‌روند؛ محیط توسعه و رازها وارد نمی‌شوند."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ("__init__.py", "app.py", "licenses.py", "upstream.py")


def copy_changed(source, target):
    data = source.read_bytes()
    if not target.exists() or target.read_bytes() != data:
        target.write_bytes(data)


def build(destination=None):
    folder = Path(destination) if destination is not None else ROOT / ".worker"
    expected = {"worker.py"} | {"gateway/" + name for name in FILES}
    if folder.exists():
        unexpected = [path for path in folder.rglob("*") if path.is_file()
                      and path.relative_to(folder).as_posix() not in expected]
        if unexpected:
            raise ValueError("پوشهٔ ساخت سرور فایل ناشناخته دارد؛ ساخت متوقف شد.")
    (folder / "gateway").mkdir(parents=True, exist_ok=True)
    for name in FILES:
        copy_changed(ROOT / name, folder / "gateway" / name)
    copy_changed(ROOT / "worker.py", folder / "worker.py")
    return folder


if __name__ == "__main__":
    build()
