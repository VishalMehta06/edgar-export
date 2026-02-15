def normalize_filings(filings):
	"""
		Returns:
		[
			{
				"accn": "...",
				"form": "10-Q",
				"filingDate": "...",
				"reports": {
					"document": [...],
					"statement": [...],
					"disclosure": [...]
				}
			}
		]
	"""
	normalized = []
	for filing in filings:
		normalized.append({
			"accn": filing["metadata"]["accn"],
			"form": filing["metadata"]["form"],
			"filingDate": filing["metadata"]["filingDate"],
			"reports": filing["reports"]
		})
	return normalized

def get_filing_types(filings):
	return sorted({
		f["metadata"]["form"]
		for f in filings
	})
