# Imports
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from datetime import datetime
import requests
import warnings

from app.logger import get_logger

logger = get_logger(__name__)


class Client:
	"""
	This class is used as the interface directly fetching data from SEC Edgar. 
	It supports the following operations:
		- Fetch the CIK of a stock given a ticker
		- Fetch a list of all filings for a stock
	"""

	def __init__(self, user_agent: str):
		self.user_agent = user_agent
		warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
		logger.debug("Client initialized with user_agent=%r", user_agent)

	def get_cik(self, ticker: str) -> str:
		"""
		Get the CIK with trailing zeros for a specified ticker. If no match is 
		found, an empty string is returned.

		:param str ticker: A string containing the ticker. The method is not 
		cap sensitive.
		"""
		cik = ""

		url = f"https://efts.sec.gov/LATEST/search-index?keysTyped={ticker}"
		headers = {
					"Host": "efts.sec.gov",
					"Sec-Ch-Ua-Platform": "\"Windows\"",
					"Accept-Language": "en-US,en;q=0.9",
					"Sec-Ch-Ua": ("\"Chromium\";v=\"135\", "
						"\"Not-A.Brand\";v=\"8\""),
					"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
						"AppleWebKit/537.36 (KHTML, like Gecko) "
						"Chrome/135.0.0.0 Safari/537.36"),
					"Sec-Ch-Ua-Mobile": "?0",
					"Accept": "*/*",
					"Origin": "https://www.sec.gov",
					"Sec-Fetch-Site": "same-site",
					"Sec-Fetch-Mode": "cors",
					"Sec-Fetch-Dest": "empty",
					"Referer": "https://www.sec.gov/",
					"Accept-Encoding": "gzip, deflate, br",
					"Connection": "keep-alive",
				}
		
		logger.debug("Fetching CIK for ticker=%r from %s", ticker, url)
		resp = requests.get(url, headers=headers)

		if resp.status_code == 200:
			results = resp.json()
			try:
				cik = results["hits"]["hits"][0]["_id"]
				cik = "0"*(10 - len(cik)) + cik
				logger.debug("Resolved CIK for %r: %s", ticker, cik)
			except (KeyError, IndexError) as e:
				logger.error(
					"Failed to parse CIK from response for ticker=%r: %s | "
					"Response: %s", ticker, e, results
				)
		else:
			logger.warning(
				"get_cik request failed for ticker=%r: HTTP %s", 
				ticker, resp.status_code
			)

		return cik
	
	def _fetch_response(self, url: str) -> requests.Response:
		"""
		Safely fetch data from a URL. Returns None if request fails.
		"""
		headers = {"User-Agent": self.user_agent}
		logger.debug("GET %s", url)
		try:
			resp = requests.get(url, headers=headers, timeout=10)
			if resp.status_code == 200:
				return resp
			logger.warning("Non-200 response from %s: HTTP %s", url, resp.status_code)
		except requests.RequestException as e:
			logger.error("Request exception for %s: %s", url, e)
		return None

	def _extract_filings(self, data: dict, filings: list[dict],
						 cutoff_date: datetime | None = None) -> bool:
		"""
		Extract filings from a JSON and merge into `filings` list.

		If `cutoff_date` is provided, only filings on or after that date are
		appended. Returns True if the oldest filing date seen in this batch is
		still within the cutoff — meaning subsequent (older) paginated files
		may still contain relevant filings. Returns False only when the oldest
		date in the batch is beyond the cutoff, at which point all further
		pages are guaranteed to be out of range too.

		Importantly, we do NOT break early on the first old filing seen within
		a batch — ordering within a chunk is not strictly guaranteed, so we
		always process the full batch and use only the oldest date as the
		pagination signal.

		When `cutoff_date` is None all filings are appended and True is returned.
		"""
		accession_numbers = data.get("accessionNumber", [])
		logger.debug("Extracting %d filings from data", len(accession_numbers))

		oldest_date_seen: datetime | None = None

		for i, accn in enumerate(accession_numbers):
			try:
				filing_date_str = data["filingDate"][i]

				if cutoff_date is not None:
					try:
						filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")
					except ValueError:
						filing_date = datetime.now()

					# Track the oldest date across the whole batch
					if oldest_date_seen is None or filing_date < oldest_date_seen:
						oldest_date_seen = filing_date

					if filing_date < cutoff_date:
						continue  # Skip appending, but keep scanning the batch

				filings.append({
					"accn": accn,
					"form": data["form"][i],
					"filingDate": filing_date_str,
					"reportDate": data["reportDate"][i]
				})
			except (KeyError, IndexError) as e:
				logger.error(
					"Failed to extract filing at index %d (accn=%r): %s", i, accn, e
				)

		if cutoff_date is None:
			return True

		# Safe to stop paginating only when the oldest date in this entire
		# batch is already beyond the cutoff
		if oldest_date_seen is None:
			return False
		return oldest_date_seen >= cutoff_date

	def get_filings(self, cik: str, 
					cutoff_date: datetime | None = None) -> list[dict]:
		"""
		Fetch a list of accession numbers for all filings given a CIK. 
		Returns a list of dicts with "form", "filingDate", and "reportDate".

		If `cutoff_date` is provided, pagination stops as soon as all filings
		in a batch are older than the cutoff — avoiding unnecessary HTTP
		requests for historical data that will never be used.

		@param str cik: The CIK of the company as a String with preceeding 
		zeros.
		@param cutoff_date: Only fetch filings on or after this date.
		"""
		filings = []
		base_url = "https://data.sec.gov/submissions"
		submissions_url = f"{base_url}/CIK{cik}.json"

		logger.info("Fetching submissions for CIK=%s", cik)
		resp = self._fetch_response(submissions_url)
		if not resp:
			logger.error(
				"Failed to fetch submissions for CIK=%s — _fetch_response "
				"returned None", cik
			)
			return filings

		submissions = resp.json()

		# Extract "recent" filings — always present, newest first
		recent_within_cutoff = self._extract_filings(
			submissions["filings"]["recent"], filings, cutoff_date
		)
		logger.debug("Extracted %d recent filings for CIK=%s", len(filings), cik)

		# If every filing in the recent block was already beyond the cutoff,
		# the extra (older) pages will be too — skip them entirely.
		if cutoff_date is not None and not recent_within_cutoff:
			logger.debug(
				"All recent filings older than cutoff for CIK=%s — "
				"skipping %d extra file(s)",
				cik, len(submissions["filings"].get("files", []))
			)
			logger.info("Total filings fetched for CIK=%s: %d", cik, len(filings))
			return filings

		# Extract older filings from additional paginated files, if any
		extra_files = submissions["filings"].get("files", [])
		logger.debug("%d additional filing file(s) found for CIK=%s", 
					 len(extra_files), cik)

		for file in extra_files:
			file_url = f"{base_url}/{file['name']}"
			resp = self._fetch_response(file_url)
			if resp:
				within_cutoff = self._extract_filings(
					resp.json(), filings, cutoff_date
				)
				# Extra files are ordered newest-first across files too.
				# Once a full batch is beyond the cutoff, all subsequent
				# files will be older still — stop paginating.
				if cutoff_date is not None and not within_cutoff:
					logger.debug(
						"Batch from %r entirely beyond cutoff — "
						"stopping pagination for CIK=%s",
						file['name'], cik
					)
					break
			else:
				logger.warning("Skipping extra filing file %r — fetch failed", 
							   file['name'])

		logger.info("Total filings fetched for CIK=%s: %d", cik, len(filings))
		return filings
	
	def get_filing_data(self, cik: str, accn: str) -> dict:
		"""
		Get a dictionary containing information on reports for a 
		specific filing and CIK.

		@param str cik: The CIK of the company as a String with preceeding 
		zeros.
		@param str accn: The Accession Number of the filing to fetch 
		information for.
		"""
		base_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}"
		base_url += f"/{accn}".replace("-", "")
		headers = {"User-Agent": self.user_agent}

		filing_summary_url = base_url + "/FilingSummary.xml"
		logger.debug("Fetching FilingSummary for accn=%r from %s", 
					 accn, filing_summary_url)

		all_reports = {}

		filing_summary_resp = requests.get(filing_summary_url, headers=headers)

		# Raises HTTPError for bad status — caller is responsible for catching
		filing_summary_resp.raise_for_status()

		filing_summary_soup = BeautifulSoup(filing_summary_resp.content, "lxml")
		reports = filing_summary_soup.find("myreports")

		if not reports:
			logger.warning("No <myreports> found in FilingSummary for accn=%r", accn)
			return all_reports

		for report in reports.find_all("report")[:-1]:
			try:
				report_dict = {}
				report_dict["name_short"] = report.shortname.text
				report_dict["name_long"] = report.longname.text
				try:
					report_dict["url"] = f"{base_url}/{report.htmlfilename.text}"
				except AttributeError:
					report_dict["url"] = f"{base_url}/{report.xmlfilename.text}"
				
				report_type = report_dict["name_long"].split(" - ")[1].strip().lower()

				if report_type in all_reports:
					all_reports[report_type].append(report_dict)
				else:
					all_reports[report_type] = [report_dict]
			except Exception as e:
				logger.error(
					"Failed to parse report entry for accn=%r: %s", accn, e, 
					exc_info=True
				)

		logger.debug(
			"Parsed %d report categories for accn=%r", len(all_reports), accn
		)
		return all_reports
