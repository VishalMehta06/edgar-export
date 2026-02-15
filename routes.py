from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from app.Stock import Stock
from app.Client import Client
import app.Utils as Utils
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

# Cache stocks to avoid re-fetching
stock_cache = {}

def get_client():
	"""Get or create a Client instance from session"""
	user_agent = session.get('user_agent')
	if not user_agent:
		return None
	return Client(user_agent)

def get_stock(ticker):
	"""Get or create a Stock instance for the given ticker"""
	client = get_client()
	if not client:
		return None
	
	ticker = ticker.upper()
	cache_key = f"{session.get('user_agent')}:{ticker}"
	
	if cache_key not in stock_cache:
		stock_cache[cache_key] = Stock(ticker=ticker, client=client)
	return stock_cache[cache_key]

@app.route("/")
def home():
	"""Home page with ticker input - check if user_agent is set"""
	if 'user_agent' not in session:
		return redirect(url_for('setup'))
	return render_template("home.html", user_name=session.get('user_name'))

@app.route("/setup", methods=["GET", "POST"])
def setup():
	"""Setup page to collect name and email"""
	if request.method == "POST":
		name = request.form.get("name", "").strip()
		email = request.form.get("email", "").strip()
		
		if name and email:
			# Store user agent in format expected by Client
			session['user_agent'] = f"{name} ({email})"
			session['user_name'] = name
			session['user_email'] = email
			return redirect(url_for('home'))
	
	return render_template("setup.html")

@app.route("/filings/<ticker>")
def filings(ticker):
	"""Display filings for a specific ticker"""
	if 'user_agent' not in session:
		return redirect(url_for('setup'))
	
	try:
		stock = get_stock(ticker)
		if not stock:
			return redirect(url_for('setup'))
			
		filings = Utils.normalize_filings(stock.filings)
		filing_types = Utils.get_filing_types(stock.filings)

		return render_template(
			"filings.html",
			filings=filings,
			filing_types=filing_types,
			ticker=stock.ticker,
			user_name=session.get('user_name')
		)
	except Exception as e:
		return render_template("error.html", ticker=ticker, error=str(e))

@app.route("/export", methods=["POST"])
def export_report():
	if 'user_agent' not in session:
		return jsonify({"status": "error", "message": "Not authenticated"}), 401
	
	data = request.json

	url = data["url"]
	ticker = data["ticker"]
	report_name = data["report_name"]
	filing_date = data["filing_date"]
	filing_type = data["filing_type"]

	safe_report = report_name.replace(" ", "_").replace("/", "-")
	filename = f"{ticker}_{safe_report}_{filing_date}_{filing_type}.xlsx"

	out_path = os.path.join(EXPORT_DIR, filename)

	stock = get_stock(ticker)
	if not stock:
		return jsonify({"status": "error", "message": "Not authenticated"}), 401
		
	stock.export_url(url, out_path)

	return jsonify({"status": "ok"})

@app.route("/logout")
def logout():
	"""Clear session and return to setup"""
	session.clear()
	return redirect(url_for('setup'))

app.run("localhost", 8080)
