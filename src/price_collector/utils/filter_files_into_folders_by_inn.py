import logging
import shutil

from pathlib import Path

from price_collector.utils.parser_inn import parser_inn

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HTML_DIR = PROJECT_ROOT / "html"
HTML_UNREAD_DIR = HTML_DIR / "unread"

logger = logging.getLogger("Utils-FilterFilesIntoFolders")


def filter_files_into_folders_by_inn():
    """Фильтрует HTML-файлы в папки по ИНН."""
    for item in HTML_UNREAD_DIR.glob("*.html"):
        inn = parser_inn(item)
        if inn is None:
            logger.warning("Не удалось определить ИНН для файла %s", item)
            continue
        folder_path = HTML_DIR / str(inn)
        try:
            is_new_folder = not folder_path.exists()
            folder_path.mkdir(parents=True, exist_ok=True)
            if is_new_folder:
                logger.info("Создана папка для ИНН %s: %s", inn, folder_path)
            shutil.move(item, folder_path / item.name)
            logger.info("Перемещён файл %s в папку %s", item.name, folder_path)
        except Exception as e:
            logger.error(
                "Ошибка при обработке файла %s для ИНН %s: %s",
                item.name,
                inn,
                e,
                )
            continue
