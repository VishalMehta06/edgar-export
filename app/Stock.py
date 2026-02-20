import pandas as pd
import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

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
		if report_category == "statement":
			# Use pandas to automatically create excel with our statement
			tables = pd.read_html(resp.text)
			df = tables[0]
			df.to_excel(f"{filename}")
		else:
			# Parse Tables and Text Blocks
			soup = BeautifulSoup(resp.text, "lxml")
			tables = self._extract_tables(soup)
			text = self._extract_text_blocks(soup)

			# Remove Garbage XBRL Tables
			tables = [t for t in tables if not self._is_xbrl_table(t[1])]

			# Write the data to excel
			wb = Workbook()
			wb.remove(wb.active)

			# Write each table to its own sheet
			for sheet_name, df in tables:
				ws = wb.create_sheet(sheet_name[:31])
				for row in dataframe_to_rows(df, index=False, header=True):
					ws.append(row)
			
			# Write text content
			ws_text = wb.create_sheet("Text_Content")
			for row in dataframe_to_rows(text, index=False, header=True):
				ws_text.append(row)

			wb.save(filename)

	def _is_xbrl_table(self, df):
		EXPECTED_FIRST_COLUMN = [
			"Name:",
			"Namespace Prefix:",
			"Data Type:",
			"Balance Type:",
			"Period Type:"
		]
		return df.iloc[:, 0].tolist() == EXPECTED_FIRST_COLUMN

	def _extract_tables(self, soup):
		"""
		Helper method to extract all tables from html reports.
		
		:param soup: The BeautifulSoup representation of the html report.
		"""
		tables = soup.find_all("table")
		extracted_tables = []

		for idx, table in enumerate(tables, start=1):
			try:
				df = pd.read_html(str(table))[0]
				extracted_tables.append((f"Table_{idx}", df))
			except ValueError:
				# Skip tables that pandas can't parse
				continue

		return extracted_tables
	
	def _extract_text_blocks(self, soup):
		"""
		Hlper method to extract all text blocks from html reports.
		
		:param soup: The BeautifulSoup representation of the html report.
		"""
		text_rows = []

		for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "div"]):
			text = tag.get_text(strip=True)
			if text:
				text_rows.append({
					"Tag": tag.name,
					"Text": text
				})

		return pd.DataFrame(text_rows)
