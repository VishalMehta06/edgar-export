import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "app.log")
LOG_LEVEL = logging.DEBUG

def get_logger(name: str) -> logging.Logger:
	"""
	Get a named logger that writes to both the log file and the console.
	All loggers share the same handlers, configured on the root 'edgar' logger.

	:param name: Typically __name__ from the calling module.
	:type name: str
	"""
	# Ensure logs directory exists
	os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

	root_logger = logging.getLogger("edgar")

	# Only add handlers once
	if not root_logger.handlers:
		root_logger.setLevel(LOG_LEVEL)

		formatter = logging.Formatter(
			fmt="[%(asctime)s] %(levelname)-8s %(name)s - %(message)s",
			datefmt="%Y-%m-%d %H:%M:%S"
		)

		# Rotating file handler — max 5MB per file, keep 3 backups
		file_handler = RotatingFileHandler(
			LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
		)
		file_handler.setLevel(LOG_LEVEL)
		file_handler.setFormatter(formatter)

		# Console handler — only WARNING and above to keep stdout clean
		console_handler = logging.StreamHandler()
		console_handler.setLevel(logging.WARNING)
		console_handler.setFormatter(formatter)

		root_logger.addHandler(file_handler)
		root_logger.addHandler(console_handler)

	return logging.getLogger(f"edgar.{name}")
