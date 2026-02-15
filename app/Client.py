# Imports
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import requests
import warnings

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
		
		resp = requests.get(url, headers=headers)

		if resp.status_code == 200:
			results = resp.json()
			
			cik = results["hits"]["hits"][0]["_id"]
			cik = "0"*(10 - len(cik)) + cik

		return cik
	
	def _fetch_response(self, url: str) -> requests.Response:
		"""
		Safely fetch JSON data from a URL. Returns None if request fails.
		"""
		headers = {"User-Agent": self.user_agent}
		try:
			resp = requests.get(url, headers=headers, timeout=10)
			if resp.status_code == 200:
				return resp
		except requests.RequestException:
			return None

	def _extract_filings(self, data: dict, filings: list[dict]) -> None:
		"""
		Extract filings from a JSON and merge into `filings` dict.
		"""
		accession_numbers = data.get("accessionNumber", [])

		for i, accn in enumerate(accession_numbers):
			filings.append({
				"accn": accn,
				"form": data["form"][i],
				"filingDate": data["filingDate"][i],
				"reportDate": data["reportDate"][i]
			})

	def get_filings(self, cik: str) -> list[dict]:
		"""
		Fetch a list of accession numbers for all filings given a CIK. 
		Returns a dict keyed by accession number with "form", "filingDate",
		and "reportDate" for each.

		@param str cik: The CIK of the company as a String with preceeding 
		zeros.
		"""
		filings = []
		base_url = "https://data.sec.gov/submissions/"
		submissions_url = f"{base_url}/CIK{cik}.json"
		submissions = self._fetch_response(submissions_url).json()

		if not submissions:
			return filings

		# Extract "recent" filings
		self._extract_filings(submissions["filings"]["recent"], filings)

		# Extract older filings from additional files, if any
		for file in submissions["filings"].get("files", []):
			file_url = f"{base_url}/{file['name']}"
			data = self._fetch_response(file_url).json()
			if data:
				self._extract_filings(data, filings)

		return filings
	
	def get_filing_data(self, cik: str, accn: str) -> dict:
		"""
		Get a dictionary containing information on reports for a 
		specific filing and CIK. The dict will distinguish types of reports 
		and for each report contain dictionaries that have the `name_short`, 
		`name_long`, and `url` of the report. 
		
		If the accn or cik is invalid, an HTTPError exception will be thrown. 
		If no reports were found when scraping, an empty list will be returned. 

		@param str cik: The CIK of the company as a String with preceeding 
		zeros.
		@param str accn: The Accession Number of the filing to fetch 
		information for.
		"""
		# Establish the base_url
		base_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}"
		base_url += f"/{accn}".replace("-", "")
		headers = headers = {"User-Agent": self.user_agent}

		# Get the summary of the filing
		filing_summary_url = base_url + "/FilingSummary.xml"

		# Collection of report metadata
		all_reports = {}

		# Parse Filing Summary for reports
		filing_summary_resp = requests.get(filing_summary_url, headers=headers)

		# If the remote resource doesn't exist, throw an HTTPError exception
		filing_summary_resp.raise_for_status()

		# Convert requests to a BeautifulSoup representation and get reports
		filing_summary_soup = BeautifulSoup(filing_summary_resp.content, "lxml")
		reports = filing_summary_soup.find("myreports")

		# Record information for each report
		for report in reports.find_all("report")[:-1]:
			report_dict = {}
			report_dict["name_short"] = report.shortname.text
			report_dict["name_long"] = report.longname.text
			try:
				report_dict["url"] = f"{base_url}/{report.htmlfilename.text}"
			except AttributeError:
				report_dict["url"] = f"{base_url}/{report.xmlfilename.text}"
			
			report_type = report_dict["name_long"].split(" - ")[1].strip().lower()

			if report_type in all_reports.keys():
				all_reports[report_type].append(report_dict)
			else:
				all_reports[report_type] = [report_dict]
		
		return all_reports
