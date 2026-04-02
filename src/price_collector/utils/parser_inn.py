"""Модуль для парсинга ИНН из HTML файлов."""
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger("InnParser")


def parser_inn(html_path: Path) -> str | None:
    """Парсит HTML файл и вытаскивает ИНН номер."""
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            match = re.search(r"ИНН[\s:]*(\d{12}|\d{10})\b", text)
            if match:
                return match.group(1)

        return None

    except FileNotFoundError:
        logger.error("Файл не найден: %s", html_path)
        return None
    except Exception as e:
        logger.error("Ошибка при чтении файла %s: %s", html_path, e)
        return None
