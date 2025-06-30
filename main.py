import logging
import json
import re
import zoneinfo
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from db import init_db, get_warnings, add_warning  # db.py faylidan importlar
ZoneInfo = zoneinfo.ZoneInfo

# --- KONFIGURATSIYA ---
TOKEN = "Your token"
WARNING_LIMIT = 3

# Logging konfiguratsiyasi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Yordamchi funksiyalar ---
def load_bad_words(file_path: str) -> list:
    """So'kinish so'zlar ro'yxatini JSON fayldan yuklaydi."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Xato: bad_words.json fayli topilmadi: {file_path}")
        return []
    except json.JSONDecodeError:
        logger.error(f"Xato: {file_path} faylida noto'g'ri JSON formati.")
        return []


def normalize_text(text: str) -> str:
    """
    Matndagi bo'sh joylar, tinish belgilari va ba'zi o'xshash belgilarni olib tashlaydi/standartlashtiradi.
    Misol: "Ali Kallen gasKe" -> "alikallengaske"
    """
    text = text.lower()
    # Bo'sh joylar va tinish belgilarini olib tashlash
    text = re.sub(r'[\s.,;\'"!@#$%^&*()-+=<>?/[\]{}|\\]', '', text)

    # Ba'zi o'xshash belgilarni almashtirish (qo'shimcha optimallash)
    text = text.replace('0', 'o')  # '0' ni 'o' ga
    text = text.replace('1', 'l')  # '1' ni 'l' ga
    text = text.replace('3', 'e')  # '3' ni 'e' ga
    text = text.replace('4', 'a')  # '4' ni 'a' ga
    text = text.replace('5', 's')  # '5' ni 's' ga
    text = text.replace('7', 't')  # '7' ni 't' ga
    text = text.replace('8', 'b')  # '8' ni 'b' ga

    return text


BAD_WORDS = load_bad_words('bad_words.json')
# Normallashtirilgan so'kinish so'zlar ro'yxatini bir marta yuklab olamiz
NORMALIZED_BAD_WORDS = [normalize_text(word) for word in BAD_WORDS]


# --- Bot buyruq handlerlari ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start buyrug'i uchun handler."""
    await update.message.reply_text(
        "Assalomu alaykum! Men guruhlarda so'kinishlarni aniqlaydigan va o'chiradigan botman."
        " Meni guruhingizga qo'shib, administrator qilib tayinlasangiz, ishga tushaman."
        " Qo'shimcha ma'lumot uchun /help buyrug'ini bosing."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help buyrug'i uchun handler."""
    await update.message.reply_text(
        "Men guruhlarda so'kinishlarni nazorat qiluvchi botman.\n\n"
        "**Asosiy funksiyalarim:**\n"
        "- So'kinishlarni avtomatik aniqlash va o'chirish.\n"
        "- So'kingan foydalanuvchilarni ogohlantirish.\n"
        "- 3 ta ogohlantirishdan keyin foydalanuvchini guruhdan chetlatish.\n\n"
        "**Buyruqlar:**\n"
        "- `/start`: Bot haqida qisqacha ma'lumot.\n"
        "- `/help`: Ushbu yordam sahifasi."
    )


# --- Xabar handlerlari ---
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guruhdagi har bir xabarni tekshiradi va so'kinishlarni aniqlaydi."""
    if not update.message or not update.message.text:
        return  # Agar xabar matni bo'lmasa, qaytish

    original_text = update.message.text
    # Xabarni normallashtiramiz
    normalized_message_text = normalize_text(original_text)
    user = update.message.from_user
    chat = update.message.chat

    # Guruh yoki superguruhda ekanligini tekshirish
    if chat.type not in ['group', 'supergroup']:
        return  # Faqat guruhlarda ishlashi uchun

    found_bad_word = False
    for normalized_bw in NORMALIZED_BAD_WORDS:  # Normallashtirilgan so'kinishlar ro'yxati bilan solishtiramiz
        if normalized_bw in normalized_message_text:
            found_bad_word = True
            break

    if found_bad_word:
        logger.info(
            f"Yashirin so'kinish aniqlandi: '{original_text}' (Normalized: '{normalized_message_text}') | Foydalanuvchi: {user.full_name} ({user.id}) | Guruh: {chat.title} ({chat.id})")

        try:
            # Xabarni o'chirish
            await update.message.delete()
        except Exception as e:
            logger.warning(
                f"Xabarni o'chirishda xatolik yuz berdi: {e}. "
                f"Botda '{chat.title}' ({chat.id}) guruhida administrator huquqlari (Delete messages) bormi?"
            )
            # Agar o'chira olmasa, foydalanuvchiga javob beramiz
            await chat.send_message(
                f"So'kinish aniqlandi! Iltimos, {user.full_name} bunday so'zlarni ishlatmang.",
                reply_to_message_id=update.message.message_id
            )

        # Ogohlantirishni ma'lumotlar bazasiga qo'shish
        current_warnings = add_warning(user.id, chat.id)

        warning_message = (
            f"🚫 **Ogohlantirish!** Hurmatli {user.full_name} ({user.id}),\n"
            f"Siz guruh qoidalarini buzdingiz va so'kinish aniqlandi.\n"
            f"Sizda **{current_warnings} ta** ogohlantirish mavjud. "
            f"**{WARNING_LIMIT} ta ogohlantirishdan so'ng siz guruhdan chetlatilasiz.**"
        )

        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=warning_message,
                parse_mode='Markdown'  # Markdown formatida yuborish
            )
        except Exception as e:
            logger.error(f"Ogohlantirish xabarini guruhga yuborishda xatolik: {e}")

        # Agar ogohlantirishlar chegaradan oshsa, foydalanuvchini guruhdan chetlatish
        if current_warnings >= WARNING_LIMIT:
            try:
                await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"🚫 Foydalanuvchi {user.full_name} ({user.id}) {WARNING_LIMIT} ta ogohlantirish olgani uchun guruhdan chetlatildi."
                )
                logger.info(
                    f"Foydalanuvchi {user.full_name} ({user.id}) '{chat.title}' ({chat.id}) guruhidan chetlatildi.")
            except Exception as e:
                logger.error(
                    f"Foydalanuvchini chetlatishda xatolik: {e}. "
                    f"Botda '{chat.title}' ({chat.id}) guruhida administrator huquqlari (Ban users) bormi?"
                )
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"⚠️ Foydalanuvchi {user.full_name} ({user.id}) ni chetlatib bo'lmadi. Botning administrator huquqlarini tekshiring."
                )


# --- Botni ishga tushirish ---
def main() -> None:
    """Botni ishga tushirish funksiyasi."""
    # Ma'lumotlar bazasini ishga tushirish
    init_db()

    # Application obyektini yaratish
    application = Application.builder().token(TOKEN).build()

    # Handlerlarni qo'shish
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_messages))

    # Botni polling rejimida ishga tushirish
    logger.info("Bot ishga tushirildi...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()