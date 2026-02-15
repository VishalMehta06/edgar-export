from flask import Flask, render_template, request, jsonify
from app.Stock import Stock
from app.Client import Client
import app.Utils as Utils
import os

app = Flask(__name__)

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

client = Client("Vishal Mehta, vvmehta06@gmail.com")
stock = Stock(ticker="AAPL", client=client)  # already initialized

@app.route("/")
def filings():
	filings = Utils.normalize_filings(stock.filings)
	filing_types = Utils.get_filing_types(stock.filings)

	return render_template(
		"filings.html",
		filings=filings,
		filing_types=filing_types,
		ticker=stock.ticker
	)

@app.route("/export", methods=["POST"])
def export_report():
	data = request.json

	url = data["url"]
	ticker = data["ticker"]
	report_name = data["report_name"]
	filing_date = data["filing_date"]
	filing_type = data["filing_type"]

	safe_report = report_name.replace(" ", "_").replace("/", "-")
	filename = f"{ticker}_{safe_report}_{filing_date}_{filing_type}.xlsx"

	out_path = os.path.join(EXPORT_DIR, filename)

	stock.export_url(url, out_path)

	return jsonify({"status": "ok"})

app.run("localhost", 8080)