# EDGAR-EXPORT

>Are you tired of trying to get data out of SEC's EDGAR database??

This tool allows you to download statements and other parts of filings as excel spreadsheets for easy access!

## How to Install

**Windows Setup**
```shell
git clone https://github.com/VishalMehta06/edgar-export
cd edgar-export
python -m venv .venv
.venv\Scripts\activate.ps1
pip install -r requirements.txt
```
*Use `python3` if that was installed instead.*

**Linux Setup**
```shell
git clone https://github.com/VishalMehta06/edgar-export
cd edgar-export
python -m venv .venv
.venv/Scripts/activate
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
http://localhost:8080
```

## Disclosures

*NOTE: This is only meant to be ran locally since there's almost certainly some vulnerabilities in this app!*

The authentication (if you can call it that) **IS NOT SECURE** and is only used to fill the user agent field of SEC EDGAR requests. 
