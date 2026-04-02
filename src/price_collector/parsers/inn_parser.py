import logging
import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger("InnParser")


def inn_parser(html_path: Path) -> Optional[str]:
    """Парсит HTML файл и вытаскивает ИНН номер."""
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            match = re.search(r"ИНН\s*(\d{10,12})", text)
            if match:
                return match.group(1)

        return None
    except Exception as e:
        logger.error("Ошибка при парсинге ИНН из %s: %s", html_path, e)
        return None