import asyncio
import time
import random

from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from config import BOT_TOKEN, CHANNEL_1_ID, CHANNEL_2_ID

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


def check_rate_limit(user_id: int):
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


def generate_math_captcha():
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    correct = a + b

    wrong_answers = set()
    while len(wrong_answers) < 3:
        candidate = correct + random.choice([-4, -3, -2, -1, 1, 2, 3, 4])
        if candidate > 0 and candidate != correct:
            wrong_answers.add(candidate)

    options = list(wrong_answers) + [correct]
    random.shuffle(options)

    question = f"{a} + {b}"
    return question, correct, options


def build_captcha_keyboard(user_id: int, options: list[int]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=str(option),
                callback_data=f"captcha:{user_id}:{option}"
            )
        ]
        for option in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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

    question, correct_answer, options = generate_math_captcha()

    captcha_storage[user_id] = {
        "answer": correct_answer,
        "question": question,
        "options": options
    }

    keyboard = build_captcha_keyboard(user_id, options)

    await message.answer(
        "🔐 Verification Required\n\n"
        f"Solve this simple question to continue:\n\n"
        f"{question} = ?",
        reply_markup=keyboard
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("captcha:"))
async def captcha_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    now = int(time.time())

    allowed, rate_remaining = check_rate_limit(user_id)
    if not allowed:
        await callback.answer(
            f"Too many requests. Wait {rate_remaining}s.",
            show_alert=True
        )
        return

    if user_id in block_storage:
        remaining_block = block_storage[user_id] - now
        if remaining_block > 0:
            await callback.answer(
                f"Temporary access blocked. Wait {remaining_block}s.",
                show_alert=True
            )
            return
        else:
            del block_storage[user_id]
            attempts_storage[user_id] = 0

    if user_id in cooldown_storage:
        remaining_cooldown = cooldown_storage[user_id] - now
        if remaining_cooldown > 0:
            await callback.answer(
                f"Cooldown active. Wait {remaining_cooldown}s.",
                show_alert=True
            )
            return
        else:
            del cooldown_storage[user_id]

    if user_id not in captcha_storage:
        await callback.answer("Verification expired. Send /start again.", show_alert=True)
        return

    try:
        _, callback_user_id, selected_value = callback.data.split(":")
        callback_user_id = int(callback_user_id)
        selected_value = int(selected_value)
    except Exception:
        await callback.answer("Invalid action.", show_alert=True)
        return

    if callback_user_id != user_id:
        await callback.answer("This verification is not for you.", show_alert=True)
        return

    correct_answer = captcha_storage[user_id]["answer"]

    if selected_value == correct_answer:
        del captcha_storage[user_id]
        attempts_storage[user_id] = 0

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

        await callback.message.edit_text(text)
        await callback.answer("Verified successfully.")
    else:
        del captcha_storage[user_id]

        attempts_storage[user_id] = attempts_storage.get(user_id, 0) + 1
        attempts_left = MAX_ATTEMPTS - attempts_storage[user_id]

        if attempts_storage[user_id] >= MAX_ATTEMPTS:
            block_storage[user_id] = now + BLOCK_SECONDS
            await callback.message.edit_text(
                f"🚫 Too many failed attempts.\n\nPlease wait {BLOCK_SECONDS} seconds before trying again."
            )
            await callback.answer("Too many failed attempts.", show_alert=True)
            return

        cooldown_storage[user_id] = now + COOLDOWN_SECONDS

        await callback.message.edit_text(
            f"❌ Incorrect answer.\n\n"
            f"Please wait {COOLDOWN_SECONDS} seconds before trying again.\n"
            f"Remaining attempts before temporary block: {attempts_left}"
        )
        await callback.answer("Incorrect answer.", show_alert=True)


@dp.message()
async def fallback_handler(message: Message):
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

    if user_id in cooldown_storage:
        remaining_cooldown = cooldown_storage[user_id] - now
        if remaining_cooldown > 0:
            await message.answer(
                f"⏳ Verification cooldown active.\n\nPlease wait {remaining_cooldown} seconds before trying again."
            )
            return

    if user_id in captcha_storage:
        await message.answer(
            "⚠️ Please use the buttons below the verification question.\n\n"
            "If your verification expired, send /start again."
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
