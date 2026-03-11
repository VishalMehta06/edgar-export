# EDGAR-EXPORT

>Are you tired of trying to get data out of SEC's EDGAR database??

This tool allows you to download statements and other parts of filings as excel spreadsheets for easy access!

## How to Install

### Windows Setup
1. Download the following constructed binary: [Windows Download](https://github.com/VishalMehta06/edgar-export/raw/refs/heads/main/dist/sec-filings-exporter.exe)
2. Double click to run
3. Navigate to `http://localhost`

### MacOS // Linux Setup
1. If using Mac, install python here: [MacOS Installer](https://www.python.org/ftp/python/3.14.3/python-3.14.3-macos11.pkg)

2. Create virtual environment for the app and install dependencies:
```shell
git clone https://github.com/VishalMehta06/edgar-export
cd edgar-export
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```
*Use `python3` if that was installed instead.*

**Running the App**
```shell
python routes.py
```

**Accessing the App**
Navigate to the following URL in google chrome!
```
http://localhost
```

## Create a Binary (For Developers)
**Windows:**
```
pyinstaller --onefile --name sec-filings-exporter --add-data "templates:templates" --add-data "static:static" --add-data "app:app" --hidden-import flask --hidden-import dotenv --hidden-import bs4 --hidden-import lxml --hidden-import lxml.etree --hidden-import lxml._elementpath --hidden-import openpyxl --hidden-import pandas routes.py
```

## Disclosures

**NOTE Regarding Network-wide Use:** This is only meant to be ran locally since there are certainly some vulnerabilities that other users on the network could abuse!

**Note Regarding Authentication:** An email and name is collected ONLY to fulfill SEC request requirements. This information is not stored in the app and is not sent to any other hosts.

**Financial Information Disclosure:** All content is for informational purposes only, you should not construe any such information or other material as legal, tax, investment, financial, or other advice.
