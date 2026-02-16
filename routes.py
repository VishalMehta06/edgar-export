from flask import Flask, render_template, request, jsonify, session, redirect, \
	url_for, send_file
from app.Stock import Stock
from app.Client import Client
import app.Utils as Utils
import os
import tempfile

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', \
								'dev-secret-key-change-in-production')

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
	category = data["category"]

	safe_report = report_name.replace(" ", "_").replace("/", "-")
	filename = f"{ticker}_{safe_report}_{filing_date}_{filing_type}.xlsx"

	stock = get_stock(ticker)
	if not stock:
		return jsonify({"status": "error", "message": "Not authenticated"}), 401
	
	# Create temporary file
	temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', 
										    delete=False)
	temp_path = temp_file.name
	temp_file.close()
	
	try:
		# Export to temporary file
		stock.export_url(url, temp_path, category)
		
		# Return the file path for download
		return jsonify({
			"status": "ok",
			"download_url": f"/download/{os.path.basename(temp_path)}",
			"filename": filename
		})
	except Exception as e:
		# Clean up temp file if export failed
		if os.path.exists(temp_path):
			os.unlink(temp_path)
		return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/download/<temp_filename>")
def download_file(temp_filename):
	"""Download exported file and clean up after"""
	if 'user_agent' not in session:
		return "Not authenticated", 401
	
	# Get the actual filename from query parameter
	filename = request.args.get('filename', 'export.xlsx')
	
	# Construct temp file path
	temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
	
	if not os.path.exists(temp_path):
		return "File not found", 404
	
	try:
		# Send file and schedule cleanup
		response = send_file(
			temp_path,
			as_attachment=True,
			download_name=filename,
			mimetype='application/vnd.openxmlformats-officedocument. \
				spreadsheetml.sheet'
		)
		
		# Clean up temp file after sending
		@response.call_on_close
		def cleanup():
			try:
				if os.path.exists(temp_path):
					os.unlink(temp_path)
			except Exception as e:
				print(f"Error cleaning up temp file: {e}")
		
		return response
	except Exception as e:
		# Clean up on error
		if os.path.exists(temp_path):
			os.unlink(temp_path)
		return str(e), 500

@app.route("/logout")
def logout():
	"""Clear session and return to setup"""
	session.clear()
	return redirect(url_for('setup'))

app.run("localhost", 8080)
