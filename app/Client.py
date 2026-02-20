# Imports
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
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

	def _extract_filings(self, data: dict, filings: list[dict]) -> None:
		"""
		Extract filings from a JSON and merge into `filings` list.
		"""
		accession_numbers = data.get("accessionNumber", [])
		logger.debug("Extracting %d filings from data", len(accession_numbers))

		for i, accn in enumerate(accession_numbers):
			try:
				filings.append({
					"accn": accn,
					"form": data["form"][i],
					"filingDate": data["filingDate"][i],
					"reportDate": data["reportDate"][i]
				})
			except (KeyError, IndexError) as e:
				logger.error(
					"Failed to extract filing at index %d (accn=%r): %s", i, accn, e
				)

	def get_filings(self, cik: str) -> list[dict]:
		"""
		Fetch a list of accession numbers for all filings given a CIK. 
		Returns a list of dicts with "form", "filingDate", and "reportDate".

		@param str cik: The CIK of the company as a String with preceeding 
		zeros.
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

		# Extract "recent" filings
		self._extract_filings(submissions["filings"]["recent"], filings)
		logger.debug("Extracted %d recent filings for CIK=%s", len(filings), cik)

		# Extract older filings from additional files, if any
		extra_files = submissions["filings"].get("files", [])
		logger.debug("%d additional filing file(s) found for CIK=%s", 
					 len(extra_files), cik)

		for file in extra_files:
			file_url = f"{base_url}/{file['name']}"
			resp = self._fetch_response(file_url)
			if resp:
				self._extract_filings(resp.json(), filings)
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
