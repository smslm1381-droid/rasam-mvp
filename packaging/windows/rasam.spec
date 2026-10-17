# فایل‌های مشتری و رازها هرگز به فهرست داده‌های بسته وارد نمی‌شوند.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

root = Path(SPECPATH).parents[1]
service = Path(os.environ["RASAM_BUILD_SERVICE_FILE"])
datas = [(str(root / "rasam/desktop/static"), "rasam/desktop/static"),
         (str(root / "templates/customer"), "templates/customer"),
         (str(service), ".")]
for package in ("langchain-core", "langchain-openai", "langgraph", "langgraph-checkpoint",
                "langgraph-prebuilt", "langsmith", "chromadb", "onnxruntime", "tokenizers"):
    datas += copy_metadata(package)
hidden = collect_submodules("chromadb")
hidden += ["keyring.backends.Windows", "uvicorn.logging", "uvicorn.loops.asyncio",
           "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on"]
analysis = Analysis([str(root / "rasam_desktop.py")], pathex=[str(root)],
                    datas=datas, hiddenimports=hidden,
                    excludes=["pytest", "gateway", "matplotlib", "IPython", "tkinter"])
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="Rasam",
          console=False, debug=False, strip=False, upx=False)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, name="Rasam", strip=False, upx=False)
