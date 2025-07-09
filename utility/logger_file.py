# utility/logger_file.py
import logging

class Logs:
    def __init__(self):
        # Set up the logger
        self.logger = logging.getLogger("InvoiceLogger")
        self.logger.setLevel(logging.DEBUG)  # Set the desired level, e.g., DEBUG, INFO

        # Avoid adding handlers multiple times if already added
        if not self.logger.handlers:

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)

            # File handler
            file_handler = logging.FileHandler("logger.log")
            file_handler.setLevel(logging.DEBUG)

            # Formatter
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)

            # Add handlers
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

    def info(self, message):
        self.logger.info(message)
    
    def error(self, message):
        self.logger.error(message)

    def debug(self, message):
        self.logger.debug(message)
