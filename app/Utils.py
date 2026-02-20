from app.logger import get_logger

logger = get_logger(__name__)


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
		try:
			normalized.append({
				"accn": filing["metadata"]["accn"],
				"form": filing["metadata"]["form"],
				"filingDate": filing["metadata"]["filingDate"],
				"reports": filing["reports"]
			})
		except KeyError as e:
			logger.error(
				"normalize_filings: missing key %s in filing=%r", e, filing
			)

	logger.debug("normalize_filings: %d filings normalized", len(normalized))
	return normalized


def get_filing_types(filings):
	try:
		types = sorted({f["metadata"]["form"] for f in filings})
		logger.debug("get_filing_types: found types=%s", types)
		return types
	except KeyError as e:
		logger.error("get_filing_types: missing key %s in filings", e)
		return []
