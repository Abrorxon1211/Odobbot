import sqlite3
import logging

DATABASE_NAME = 'warnings.db'
logger = logging.getLogger(__name__)


def init_db():
    """Ma'lumotlar bazasini ishga tushiradi va kerakli jadvallarni yaratadi."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_warnings (
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                warning_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        conn.commit()
        logger.info("Ma'lumotlar bazasi ishga tushirildi va 'user_warnings' jadvali yaratildi/tekshirildi.")
    except sqlite3.Error as e:
        logger.error(f"Ma'lumotlar bazasini ishga tushirishda xatolik: {e}")
    finally:
        if conn:
            conn.close()


def get_warnings(user_id: int, chat_id: int) -> int:
    """Foydalanuvchining ma'lum guruhdagi ogohlantirishlari sonini qaytaradi."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT warning_count FROM user_warnings WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.Error as e:
        logger.error(f"Ogohlantirishlarni olishda xatolik: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def add_warning(user_id: int, chat_id: int) -> int:
    """Foydalanuvchiga ogohlantirish qo'shadi va yangi ogohlantirish sonini qaytaradi."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        current_warnings = get_warnings(user_id, chat_id)
        new_warnings = current_warnings + 1

        cursor.execute(
            '''INSERT OR REPLACE INTO user_warnings (user_id, chat_id, warning_count)
               VALUES (?, ?, ?)''',
            (user_id, chat_id, new_warnings)
        )
        conn.commit()
        logger.info(f"Foydalanuvchi {user_id} ({chat_id} guruhida) ogohlantirildi. Yangi soni: {new_warnings}")
        return new_warnings
    except sqlite3.Error as e:
        logger.error(f"Ogohlantirish qo'shishda xatolik: {e}")
        return current_warnings # Xato bo'lsa, oldingi sonni qaytaramiz
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    # Faylni to'g'ridan-to'g'ri ishga tushirganda DB ni yaratish uchun
    logging.basicConfig(level=logging.INFO)
    init_db()