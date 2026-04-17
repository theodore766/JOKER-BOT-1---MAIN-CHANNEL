import asyncio
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.types import Message, ChatJoinRequest
from aiogram.filters import CommandStart

from config import BOT_TOKEN, LOG_GROUP_ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Welcome.\n\n"
        "Use the links in the channel to join."
    )


@dp.chat_join_request()
async def handle_join_request(join_request: ChatJoinRequest):
    user = join_request.from_user
    chat = join_request.chat

    username = f"@{user.username}" if user.username else "No username"
    first_name = user.first_name or "No first name"
    last_name = user.last_name or ""

    joined_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    log_text = (
        "✅ New Member Approved\n\n"
        f"Name: {first_name} {last_name}\n"
        f"Username: {username}\n"
        f"User ID: {user.id}\n"
        f"Chat: {chat.title}\n"
        f"Chat ID: {chat.id}\n"
        f"Time: {joined_at}"
    )

    # envia log
    await bot.send_message(LOG_GROUP_ID, log_text)

    # aprova automaticamente
    await bot.approve_chat_join_request(
        chat_id=chat.id,
        user_id=user.id
    )


@dp.message()
async def fallback_handler(message: Message):
    await message.answer("Use the channel links to join.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
