"""Модуль для взаимодействия с почтовым сервером Яндекса через IMAP."""
import imaplib
import logging
import os
from datetime import datetime
from email import message_from_bytes
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("YandexEmailClient")

HTML_OUTPUT_DIR = Path("html")


class YandexEmailClient:
    """Клиент для подключения к почтовому серверу Яндекса и извлечения
    HTML-содержимого.

    Для настройки клиента необходимо задать следующие переменные окружения:
    - {MAIL_NAME}_IMAP_SERVER: Адрес IMAP-сервера (например, imap.yandex.ru)
    - {MAIL_NAME}_IMAP_PORT: Порт IMAP-сервера (обычно 993)
    - {MAIL_NAME}_EMAIL: Адрес электронной почты для подключения
    - {MAIL_NAME}_EMAIL_PASSWORD: Пароль от электронной почты

    Args:
        mail_name (str): Префикс для переменных окружения,
            определяющий настройки подключения.

    """

    def __init__(self, mail_name: str) -> None:
        """Инициализация клиента с настройками из переменных окружения."""
        self.mail: imaplib.IMAP4_SSL | None = None
        self.imap_server: str | None = None
        self.imap_port: int | None = None
        self.email: str | None = None
        self.password: str | None = None
        self._set_configuration(mail_name.upper())

    def _set_configuration(self, mail_name: str) -> None:
        """Загрузка конфигурации из переменных окружения."""
        server_config = self._check_configuration(mail_name)

        self.imap_server = str(server_config["IMAP_SERVER"])
        self.imap_port = int(server_config["IMAP_PORT"])
        self.email = str(server_config["EMAIL"])
        self.password = str(server_config["EMAIL_PASSWORD"])

    @staticmethod
    def _check_configuration(name: str) -> dict:
        """Проверка наличия всех необходимых переменных окружения."""
        required_vars = {
            "IMAP_SERVER": os.getenv(f"{name}_IMAP_SERVER"),
            "IMAP_PORT": os.getenv(f"{name}_IMAP_PORT"),
            "EMAIL": os.getenv(f"{name}_EMAIL"),
            "EMAIL_PASSWORD": os.getenv(f"{name}_EMAIL_PASSWORD"),
        }

        missing = [k for k, v in required_vars.items() if not v]

        if missing:
            error_message = (
                f"Недостаточно данных для настройки клиента '{name}'. "
                f"{', '.join(f'{name}_{m}' for m in missing)}"
            )
            logger.error(error_message)
            raise ValueError(error_message)

        return required_vars

    def _connect(self) -> None:
        """Установка соединения с почтовым сервером и авторизация."""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.email, self.password)
            logger.info("Успешное подключение к почтовому серверу")
        except (imaplib.IMAP4.error, OSError) as e:
            error_message = (
                f"Ошибка при подключении к почтовому серверу: {e}"
                )
            logger.exception(error_message)
            raise ConnectionError(error_message) from e

    def _disconnect(self) -> None:
        """Корректное отключение от почтового сервера."""
        if self.mail:
            try:
                self.mail.logout()
                logger.info("Успешное отключение от почтового сервера")
            except imaplib.IMAP4.error as e:
                logger.exception(
                    "Ошибка при отключении от почтового сервера: %s",
                    e,
                    )
            finally:
                self.mail = None

    def retrieve_unread_emails_from_folder(
            self,
            folder_name: str) -> list[Path]:
        """Извлечение непрочитанных писем из указанной папки.

        Сохраняет HTML-содержимое в файлы и возвращает
        список путей к этим файлам.
        """
        saved_files: list[Path] = []
        try:
            self._connect()
            status, _ = self.mail.select(folder_name)

            if status != "OK":
                logger.error("Ошибка при открытии папки %s", folder_name)
                return saved_files

            status, messages = self.mail.search(None, "UNSEEN")

            if status != "OK":
                logger.error("Ошибка при поиске писем в папке %s", folder_name)
                return saved_files

            email_ids = messages[0].split()

            if not email_ids:
                logger.info("Нет новых писем в папке %s", folder_name)
                return saved_files

            logger.info(
                "Найдено %d новых писем в папке %s",
                len(email_ids),
                folder_name,
            )
            for email_id in email_ids:
                filepath = self._fetch_email_content(email_id)
                if filepath:
                    saved_files.append(filepath)

            return saved_files
        except ConnectionError:
            raise
        except Exception as e:
            error_message = (
                f"Ошибка при чтении писем из папки {folder_name}: {e}"
                )
            logger.exception(error_message)
            raise RuntimeError(error_message) from e
        finally:
            self._disconnect()

    def _fetch_email_content(self, email_id: bytes) -> Path | None:
        """Получение содержимого письма по его ID.

        Извлекает HTML-часть и сохраняет её в файл.
        Возвращает путь к файлу или None в случае ошибки.
        """
        try:
            status, msg_data = self.mail.fetch(email_id, "(RFC822)")

            if status != "OK":
                logger.error("Ошибка при получении письма с ID %s", email_id)
                return None

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    email_message = message_from_bytes(response_part[1])
                    for part in email_message.walk():
                        if part.get_content_type() == "text/html":
                            payload = part.get_payload(decode=True)
                            if payload is None:
                                logger.warning(
                                    "Пустое содержимое HTML "
                                    "в письме %s",
                                    email_id,
                                )
                                return None
                            html_content = payload.decode(
                                "utf-8",
                                errors="replace",
                                )
                            filename = (
                                self._generate_unique_filename(email_id)
                                )
                            return self._save_html_file(filename, html_content)
            return None
        except Exception as e:
            logger.error(
                "Ошибка при обработке письма с ID %s: %s",
                email_id,
                e,
                )
            return None

    @staticmethod
    def _save_html_file(filename: str, html_content: str) -> Path | None:
        """Сохранение HTML-содержимого в файл.

        Возвращает путь к файлу или None в случае ошибки.
        """
        try:
            HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            filepath = HTML_OUTPUT_DIR / filename
            filepath.write_text(html_content, encoding="utf-8")
            logger.info(
                "HTML-содержимое письма сохранено в файл: %s",
                filepath,
            )
            return filepath
        except Exception as e:
            logger.exception(
                "Ошибка при сохранении HTML-содержимого "
                "в файл %s: %s",
                filename,
                e,
            )
            return None

    @staticmethod
    def _generate_unique_filename(email_id: bytes) -> str:
        """Генерация уникального имени файла на основе ID письма."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id = email_id.decode("utf-8", errors="replace").strip()
        return f"email_{timestamp}_{safe_id}.html"
