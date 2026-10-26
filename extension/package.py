"""Packs the browser extension into frontend/public/careerops-extension.zip, served by the app on the
"Instalar extensão" page. Run after changing the extension:  python3 extension/package.py"""
import json
import pathlib
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "frontend" / "public" / "careerops-extension.zip"
FILES = ["manifest.json", "background.js", "content.js", "content.css", "profile_filler.js", "popup.html", "popup.js"]

version = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))["version"]
OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    # Everything under one folder, so "extract here" gives a folder to select in chrome://extensions
    for name in FILES:
        z.write(HERE / name, f"careerops-extension/{name}")
    for icon in sorted((HERE / "icons").iterdir()):
        z.write(icon, f"careerops-extension/icons/{icon.name}")
(OUT.parent / "careerops-extension.json").write_text(json.dumps({"version": version}), encoding="utf-8")
print(f"wrote {OUT} (version {version})")
