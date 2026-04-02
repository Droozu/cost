import imaplib
import os
import logging

from dotenv import load_dotenv
from email import message_from_bytes

from src.price_collector.cli.log_setup import setup_logging

load_dotenv()
logger = logging.getLogger("YandexEmailClient")

class YandexEmailClient:
    def __init(self):
        self.mail = None
        self.IMAP_SERVER = None
        self.IMAP_PORT = None
        self.EMAIL = None
        self.PASSWORD = None

    def set_configuration(self, mail_name):
        name = mail_name.upper()
        self.IMAP_SERVER = os.getenv(f"{name}_IMAP_SERVER")
        self.IMAP_PORT = os.getenv(f"{name}_IMAP_PORT")
        self.EMAIL = os.getenv(f"{name}_EMAIL")
        self.PASSWORD = os.getenv(f"{name}_EMAIL_PASSWORD")

    def connect(self):
        try:
            self.mail = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
            self.mail.login(self.EMAIL, self.PASSWORD)
            logger.info("Успешное подключение к почтовому серверу")
        except Exception as e:
            logger.info(f"Ошибка при подключении к почтовому серверу: {e}")

    def disconnect(self):
        if self.mail:
            try:
                self.mail.logout()
                logger.info("Успешное отключение от почтового сервера")
            except Exception as e:
                logger.info(f"Ошибка при отключении от почтового сервера: {e}")

    def save_email_content(self, folder_name):
        try:
            self.connect()
            self.mail.select(folder_name)
            status, messages = self.mail.search(None, "UNSEEN")
            
            if status != "OK":
                self.disconnect()
                logger.info("Ошибка при поиске писем")
                return
            
            email_ids = messages[0].split()

            if not email_ids:
                self.disconnect()
                logger.info(f"Нет новых писем в папке {folder_name}")
                return
            
            logger.info(f"Найдено {len(email_ids)} новых писем в папке {folder_name}")
            
            for index, email_id in enumerate(email_ids):
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        try:
                            email_message = message_from_bytes(response_part[1])
                            for part in email_message.walk():
                                if part.get_content_type() == "text/html":
                                    html_content = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                    filename = f"email_{index + 1}.html"
                                    self._save_html_file(filename, html_content)
                                    break
                        except Exception as e:
                            logger.info(f"Ошибка при обработке письма: {e}")
            self.disconnect()
        except Exception as e:
            logger.info(f"Ошибка при чтении писем: {e}")

    def _save_html_file(self, filename, html_content):
        try:
            with open(f"html/{filename}", "w", encoding="utf-8") as file:
                file.write(html_content)
            logger.info(f"HTML-содержимое письма сохранено в файл: {filename}")
        except Exception as e:
            logger.info(f"Ошибка при сохранении HTML-содержимого в файл: {e}")          
