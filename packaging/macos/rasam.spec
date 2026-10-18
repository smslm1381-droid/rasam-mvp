# بستهٔ مک از همان هسته و رابط رومیزی استفاده می‌کند؛ اطلاعات مشتری دادهٔ بسته نیست.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

root = Path(SPECPATH).parents[1]
service = Path(os.environ["RASAM_BUILD_SERVICE_FILE"])
datas = [(str(root / "rasam/desktop/static"), "rasam/desktop/static"),
         (str(root / "templates/customer"), "templates/customer"), (str(service), ".")]
for package in ("langchain-core", "langchain-openai", "langgraph", "langgraph-checkpoint",
                "langgraph-prebuilt", "langsmith", "chromadb", "onnxruntime", "tokenizers"):
    datas += copy_metadata(package)
hidden = collect_submodules("chromadb")
hidden += ["keyring.backends.macOS", "uvicorn.logging", "uvicorn.loops.asyncio",
           "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on"]
analysis = Analysis([str(root / "rasam_desktop.py")], pathex=[str(root)],
                    datas=datas, hiddenimports=hidden,
                    excludes=["pytest", "gateway", "matplotlib", "IPython", "tkinter"])
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="Rasam",
          console=False, debug=False, strip=False, upx=False,
          target_arch=os.environ["RASAM_BUILD_ARCH"], codesign_identity=None)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, name="Rasam", strip=False, upx=False)
app = BUNDLE(bundle, name="Rasam.app", icon=str(root / "assets/brand/rasam.icns"),
             bundle_identifier="com.rasam.desktop",
             info_plist={"CFBundleName": "Rasam", "CFBundleDisplayName": "رصام",
                         "CFBundleShortVersionString": os.environ["RASAM_BUILD_VERSION"],
                         "CFBundleVersion": os.environ["RASAM_BUILD_VERSION"],
                         "NSAppleEventsUsageDescription": "برای نمایش تب باز رصام به‌جای ساختن تب تکراری، اجازهٔ دسترسی به مرورگر لازم است.",
                         "NSHighResolutionCapable": True})
