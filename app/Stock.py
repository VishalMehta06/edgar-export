import requests
import pandas as pd

import traceback

from app.Client import Client

class Stock:
	"""
	Organize the results for a single stock unit.
	"""

	def __init__(self, client: Client, ticker: str, 
			  	 filing_forms: list[str] = ["10-K", "10-Q"]):
		"""		
		:param ticker: The ticker of the stock. Capitalization doesn't matter.
		:type ticker: str
		:param client: The client to be used to fetch data.
		:type client: Client
		:param filing_forms: A list of strings of filing 'form's to track.
		:type filing_forms: list[str]
		"""
		self.ticker = ticker.upper()
		self.client = client
		self.cik = client.get_cik(ticker)
		self.filings = self._init_filings(filing_forms)

	def _init_filings(self, filing_forms: list[str]) -> list[dict]:
		"""
		Initialize self.filings. 
		
		:param filing_forms: A list of strings of filing 'form's to track.
		:type filing_forms: list[str]
		"""
		all_filings = self.client.get_filings(self.cik)
		selected_filings = []

		for filing in all_filings:
			if filing["form"] in filing_forms:
				try:
					data = self.client.get_filing_data(self.cik, filing["accn"])
					selected_filings.append({"metadata": filing, 
							  				 "reports": data})
				except:
					# Filings causing any error have not been indexed in a 
					# similar way, we must ignore them.
					pass
		
		return selected_filings
	
	def export_url(self, url: str, filename: str, 
				   report_category: str = "statement") -> None:
		"""
		Export a report from a URL to excel.

		:param url: The URL of the report
		:type url: str
		:param filename: The output filename
		:type filename: str
		:param report_category: The category of the report. Either "document", 
		"statement", or "disclosure". If it is not supplied, it is assumed the 
		report is a "statement". 
		:type report_category: str 
		"""
		resp = self.client._fetch_response(url)
		tables = pd.read_html(resp.text)
		if report_category == "statement":
			df = tables[0]
			df.to_excel(f"{filename}")
		elif report_category == "disclosure" or report_category == "document":
			with pd.ExcelWriter(filename, "openpyxl") as writer:
				[t.to_excel(writer, f"Sheet {i+1}") 
	 			 for i, t in enumerate(tables)]
