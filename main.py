import asyncio
import time
import os

from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart

from config import BOT_TOKEN, CHANNEL_1_ID, CHANNEL_2_ID
from captcha_utils import generate_captcha

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

captcha_storage = {}
cooldown_storage = {}
attempts_storage = {}
block_storage = {}
rate_limit_storage = {}

MAX_ATTEMPTS = 3
COOLDOWN_SECONDS = 15
BLOCK_SECONDS = 60

RATE_LIMIT_SECONDS = 3
RATE_LIMIT_MAX_MESSAGES = 4
RATE_LIMIT_BLOCK_SECONDS = 20


def check_rate_limit(user_id):
    now = time.time()

    if user_id in rate_limit_storage:
        user_data = rate_limit_storage[user_id]

        if "blocked_until" in user_data:
            if now < user_data["blocked_until"]:
                remaining = int(user_data["blocked_until"] - now)
                if remaining < 1:
                    remaining = 1
                return False, remaining
            else:
                rate_limit_storage[user_id] = {
                    "messages": [],
                    "blocked_until": 0
                }

    if user_id not in rate_limit_storage:
        rate_limit_storage[user_id] = {
            "messages": [],
            "blocked_until": 0
        }

    user_data = rate_limit_storage[user_id]

    user_data["messages"] = [
        msg_time for msg_time in user_data["messages"]
        if now - msg_time <= RATE_LIMIT_SECONDS
    ]

    user_data["messages"].append(now)

    if len(user_data["messages"]) > RATE_LIMIT_MAX_MESSAGES:
        user_data["blocked_until"] = now + RATE_LIMIT_BLOCK_SECONDS
        remaining = int(RATE_LIMIT_BLOCK_SECONDS)
        return False, remaining

    return True, 0


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    now = int(time.time())

    allowed, rate_remaining = check_rate_limit(user_id)
    if not allowed:
        await message.answer(
            f"🚫 Too many requests detected.\n\nPlease wait {rate_remaining} seconds before trying again."
        )
        return

    if user_id in block_storage:
        remaining_block = block_storage[user_id] - now
        if remaining_block > 0:
            await message.answer(
                f"🚫 Temporary access blocked.\n\nPlease wait {remaining_block} seconds before trying again."
            )
            return
        else:
            del block_storage[user_id]
            attempts_storage[user_id] = 0

    if user_id in cooldown_storage:
        remaining_cooldown = cooldown_storage[user_id] - now
        if remaining_cooldown > 0:
            await message.answer(
                f"⏳ Verification cooldown active.\n\nPlease wait {remaining_cooldown} seconds before trying again."
            )
            return
        else:
            del cooldown_storage[user_id]

    code, image_path = generate_captcha(user_id)
    captcha_storage[user_id] = code

    photo = FSInputFile(image_path)

    await message.answer_photo(
        photo=photo,
        caption=(
            "🔐 Verification Required\n\n"
            "Please type the code shown in the image to continue."
        )
    )


@dp.message()
async def captcha_check(message: Message):
    user_id = message.from_user.id
    now = int(time.time())

    allowed, rate_remaining = check_rate_limit(user_id)
    if not allowed:
        await message.answer(
            f"🚫 Too many requests detected.\n\nPlease wait {rate_remaining} seconds before trying again."
        )
        return

    if user_id in block_storage:
        remaining_block = block_storage[user_id] - now
        if remaining_block > 0:
            await message.answer(
                f"🚫 Temporary access blocked.\n\nPlease wait {remaining_block} seconds before trying again."
            )
            return
        else:
            del block_storage[user_id]
            attempts_storage[user_id] = 0

    if user_id in cooldown_storage:
        remaining_cooldown = cooldown_storage[user_id] - now
        if remaining_cooldown > 0:
            await message.answer(
                f"⏳ Verification cooldown active.\n\nPlease wait {remaining_cooldown} seconds before trying again."
            )
            return
        else:
            del cooldown_storage[user_id]

    if user_id not in captcha_storage:
        return

    correct_code = captcha_storage[user_id]
    user_text = (message.text or "").strip().upper()

    image_path = f"captcha_{user_id}.png"

    if user_text == correct_code:
        del captcha_storage[user_id]
        attempts_storage[user_id] = 0

        if os.path.exists(image_path):
            os.remove(image_path)

        expire_time = int(time.time()) + 30

        link1 = await bot.create_chat_invite_link(
            chat_id=CHANNEL_1_ID,
            expire_date=expire_time,
            member_limit=1
        )

        link2 = await bot.create_chat_invite_link(
            chat_id=CHANNEL_2_ID,
            expire_date=expire_time,
            member_limit=1
        )

        text = f"""✅ Access Verified

Welcome. Your access has been successfully granted.

📢 Main Channel:
{link1.invite_link}

🛍️ Storelist:
{link2.invite_link}

📌 How to Join
1. Open the Main Channel link
2. Join the channel immediately
3. Open the Storelist link
4. Join before the links expire
5. If one link does not open, try the other one immediately first

⚠️ Important
• Each link can be used only once
• Links expire in 30 seconds
• Join both channels as soon as possible

📞 Support
If you have any issues, contact support here:
https://t.me/jokerrefundss
"""

        await message.answer(text)

    else:
        del captcha_storage[user_id]

        if os.path.exists(image_path):
            os.remove(image_path)

        attempts_storage[user_id] = attempts_storage.get(user_id, 0) + 1
        attempts_left = MAX_ATTEMPTS - attempts_storage[user_id]

        if attempts_storage[user_id] >= MAX_ATTEMPTS:
            block_storage[user_id] = now + BLOCK_SECONDS
            await message.answer(
                f"🚫 Too many failed attempts.\n\nPlease wait {BLOCK_SECONDS} seconds before trying again."
            )
            return

        cooldown_storage[user_id] = now + COOLDOWN_SECONDS

        await message.answer(
            f"❌ Incorrect code.\n\n"
            f"Please wait {COOLDOWN_SECONDS} seconds before trying again.\n"
            f"Remaining attempts before temporary block: {attempts_left}"
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
