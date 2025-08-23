import os
import logging
import tempfile
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения
TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    logger.error("Не задан BOT_TOKEN в переменных окружения!")
    raise ValueError("Не задан BOT_TOKEN в переменных окружения!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = f"""
Привет, {user.first_name}! 👋

Я бот для генерации конфигурационных файлов Cloudflare WARP.

Используй команду /generate чтобы получить свой конфиг файл.

После получения файла, ты можешь использовать его в приложениях, поддерживающих WARP.
    """
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def generate_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерация конфигурационного файла WARP"""
    try:
        # Создаем временную директорию для работы
        with tempfile.TemporaryDirectory() as temp_dir:
            # Уведомляем пользователя о начале процесса
            message = await update.message.reply_text("⏳ Начинаю генерацию конфигурации WARP...")
            
            # Устанавливаем wgcf если не установлен
            wgcf_path = install_wgcf(temp_dir)
            
            # Регистрируем новый аккаунт
            await message.edit_text("📝 Регистрирую новый аккаунт WARP...")
            register_result = subprocess.run(
                [wgcf_path, "register", "--accept-tos"],
                capture_output=True,
                text=True,
                cwd=temp_dir
            )
            
            if register_result.returncode != 0:
                logger.error(f"Ошибка регистрации: {register_result.stderr}")
                await message.edit_text("❌ Ошибка при регистрации аккаунта. Попробуйте позже.")
                return
            
            # Генерируем конфигурационный файл
            await message.edit_text("🔧 Генерирую конфигурационный файл...")
            generate_result = subprocess.run(
                [wgcf_path, "generate"],
                capture_output=True,
                text=True,
                cwd=temp_dir
            )
            
            if generate_result.returncode != 0:
                logger.error(f"Ошибка генерации: {generate_result.stderr}")
                await message.edit_text("❌ Ошибка при генерации конфигурации. Попробуйте позже.")
                return
            
            # Читаем сгенерированный конфиг
            config_path = os.path.join(temp_dir, "wgcf-profile.conf")
            if not os.path.exists(config_path):
                await message.edit_text("❌ Конфигурационный файл не был создан.")
                return
            
            with open(config_path, "r") as f:
                config_content = f.read()
            
            # Отправляем конфиг пользователю
            await message.edit_text("✅ Конфигурация готова! Отправляю файл...")
            
            # Сохраняем конфиг в временный файл для отправки
            with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as tmp_file:
                tmp_file.write(config_content)
                tmp_file.flush()
                
                with open(tmp_file.name, "rb") as file_to_send:
                    await update.message.reply_document(
                        document=file_to_send,
                        caption="Ваш конфигурационный файл WARP\n\nИспользуйте его в поддерживаемых приложениях.",
                        filename="warp.conf"
                    )
            
            os.unlink(tmp_file.name)
            await message.delete()
            
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await update.message.reply_text("❌ Произошла непредвиденная ошибка. Попробуйте позже.")

def install_wgcf(temp_dir: str) -> str:
    """Установка wgcf в временную директорию"""
    wgcf_path = os.path.join(temp_dir, "wgcf")
    
    # Скачиваем wgcf
    subprocess.run([
        "curl", "-fsSL", "https://github.com/ViRb3/wgcf/releases/download/v2.2.18/wgcf_2.2.18_linux_amd64",
        "-o", wgcf_path
    ], check=True)
    
    # Делаем исполняемым
    subprocess.run(["chmod", "+x", wgcf_path], check=True)
    
    return wgcf_path

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = """
🤖 <b>Команды бота:</b>

/start - Начать работу с ботом
/generate - Сгенерировать конфигурационный файл WARP
/help - Показать эту справку

🔧 <b>Как использовать:</b>

1. Используйте команду /generate чтобы получить конфигурационный файл
2. Сохраните файл и используйте его в поддерживаемом клиенте WARP
3. Наслаждайтесь безопасным подключением через Cloudflare WARP!

📝 <b>Примечание:</b>
Каждый конфиг привязан к уникальному аккаунту WARP.
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

def main() -> None:
    """Запуск бота"""
    # Создаем Application
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate_config))
    application.add_handler(CommandHandler("help", help_command))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()
