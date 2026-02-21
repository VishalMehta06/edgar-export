from flask import Flask, render_template, request, jsonify, session, redirect, \
	url_for, send_file
from app.Stock import Stock
from app.Client import Client
from app.logger import get_logger
import app.Utils as Utils
import os
import tempfile
import threading

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
	raise RuntimeError(
		"SECRET_KEY is not set. Please define it in your .env file."
	)

logger = get_logger(__name__)

# Cache stocks by (ticker, years) — shared across all users.
# _cache_locks ensures that if two requests arrive for the same key
# simultaneously, only one builds the Stock while the other waits,
# rather than both building in parallel and racing to write the cache.
stock_cache: dict = {}
_cache_locks: dict[tuple, threading.Lock] = {}
_locks_lock = threading.Lock()  # guards _cache_locks itself


def _get_lock(cache_key: tuple) -> threading.Lock:
	"""Return the per-cache-key lock, creating it if necessary."""
	with _locks_lock:
		if cache_key not in _cache_locks:
			_cache_locks[cache_key] = threading.Lock()
		return _cache_locks[cache_key]


def get_client():
	"""Get or create a Client instance from session"""
	user_agent = session.get('user_agent')
	if not user_agent:
		return None
	return Client(user_agent)


def get_stock(ticker, years=10):
	"""Get or create a Stock instance for the given ticker and year window.

	The cache is keyed by (ticker, years). A per-key lock ensures that
	concurrent requests for the same ticker/years pair block until the
	first request has finished building the Stock and written it to the
	cache, rather than each building their own copy in parallel and
	mutating a partially-constructed shared object.
	"""
	client = get_client()
	if not client:
		return None

	ticker = ticker.upper()
	cache_key = (ticker, years)

	# Fast path — already cached, no lock needed for a read
	if cache_key in stock_cache:
		logger.debug("Cache hit for ticker=%s years=%d", ticker, years)
		return stock_cache[cache_key]

	# Slow path — acquire the per-key lock so only one thread builds
	lock = _get_lock(cache_key)
	with lock:
		# Re-check inside the lock: another thread may have built it
		# while we were waiting
		if cache_key in stock_cache:
			logger.debug(
				"Cache hit (post-lock) for ticker=%s years=%d", ticker, years
			)
			return stock_cache[cache_key]

		logger.info(
			"Cache miss for ticker=%s years=%d — building Stock", ticker, years
		)
		# Build fully before inserting — no other thread can see a
		# half-constructed object
		stock = Stock(ticker=ticker, client=client, years=years)
		stock_cache[cache_key] = stock

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
			session['user_agent'] = f"{name} ({email})"
			session['user_name'] = name
			session['user_email'] = email
			logger.info("New session created for user=%r email=%r", name, email)
			return redirect(url_for('home'))
	
	return render_template("setup.html")

@app.route("/filings/<ticker>")
def filings(ticker):
	"""Display filings for a specific ticker"""
	if 'user_agent' not in session:
		return redirect(url_for('setup'))
	
	try:
		# Read years from query string; clamp to a sane range
		try:
			years = int(request.args.get('years', 10))
			years = max(1, min(years, 30))
		except (ValueError, TypeError):
			years = 10

		stock = get_stock(ticker, years=years)
		if not stock:
			return redirect(url_for('setup'))

		logger.info(
			"Rendering filings for ticker=%s years=%d: %d filing(s)", 
			ticker, years, len(stock.filings)
		)

		normalized = Utils.normalize_filings(stock.filings)
		filing_types = Utils.get_filing_types(stock.filings)

		return render_template(
			"filings.html",
			filings=normalized,
			filing_types=filing_types,
			ticker=stock.ticker,
			years=years,
			user_name=session.get('user_name')
		)
	except Exception as e:
		logger.exception("Unhandled error in /filings/%s", ticker)
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

	logger.info(
		"Export requested: ticker=%s report=%s date=%s type=%s",
		ticker, report_name, filing_date, filing_type
	)
	
	temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', 
										    delete=False)
	temp_path = temp_file.name
	temp_file.close()
	
	try:
		stock.export_url(url, temp_path, category)
		logger.info("Export succeeded: temp_path=%s filename=%s", temp_path, filename)
		return jsonify({
			"status": "ok",
			"download_url": f"/download/{os.path.basename(temp_path)}",
			"filename": filename
		})
	except Exception as e:
		logger.exception("Export failed for ticker=%s url=%s", ticker, url)
		if os.path.exists(temp_path):
			os.unlink(temp_path)
		return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/download/<temp_filename>")
def download_file(temp_filename):
	"""Download exported file and clean up after"""
	if 'user_agent' not in session:
		return "Not authenticated", 401
	
	filename = request.args.get('filename', 'export.xlsx')
	temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
	
	if not os.path.exists(temp_path):
		logger.warning("Download requested but temp file not found: %s", temp_path)
		return "File not found", 404
	
	try:
		response = send_file(
			temp_path,
			as_attachment=True,
			download_name=filename,
			mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
		)
		
		@response.call_on_close
		def cleanup():
			try:
				if os.path.exists(temp_path):
					os.unlink(temp_path)
					logger.debug("Cleaned up temp file: %s", temp_path)
			except Exception as e:
				logger.error("Error cleaning up temp file %s: %s", temp_path, e)
		
		return response
	except Exception as e:
		logger.exception("Error sending file %s", temp_path)
		if os.path.exists(temp_path):
			os.unlink(temp_path)
		return str(e), 500

@app.route("/logout")
def logout():
	"""Clear session and return to setup"""
	user = session.get('user_name')
	session.clear()
	logger.info("User %r logged out", user)
	return redirect(url_for('setup'))

app.run("localhost", 80)
