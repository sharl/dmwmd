# dmwmd

Don't mess with my desktop (DMWMD)

## Run

```powershell
git clone https://github.com/sharl/dmwmd.git
cd dmwmd
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python dmwmd.py
```

## Build

```powershell
pip install pyinstaller
pyinstaller "dmwmd.py" "--onefile" "--noconsole" "--icon=Assets/sample.ico" "--exclude-module=PIL._avif" "--exclude-module=PIL._imagingcms" "--exclude-module=PIL._webp" "--exclude-module=winrt.windows.globalization" "--exclude-module=winrt.windows.media.core" "--exclude-module=winrt.windows.media.ocr" "--exclude-module=winrt.windows.media.playback" "--exclude-module=winrt.windows.media.speechsynthesis" "--add-data=Assets/version.txt;Assets" "--add-data=Assets/sample.ico;Assets"
```
