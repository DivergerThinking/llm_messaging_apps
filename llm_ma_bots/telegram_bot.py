import logging
import os
from collections import defaultdict

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Point to the local server
client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

# This dictionaty stores the messages. The key is the chat_id and the value is a list of messages.
chat_history = defaultdict(list)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi I'm a bot, how can I help?")


async def update_and_get_chat_history(message: str, chat_id: int, top_k_messages: int = 5) -> list:
    chat_history[chat_id].append(message)
    return chat_history[chat_id][-top_k_messages:-1]


async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, with_context: bool = True):
    chat_id = update.effective_chat.id
    message = update.effective_message.text

    history = await update_and_get_chat_history(message, chat_id)

    if with_context:
        str_history = "\n".join(history)
        formatted_prompt = f"Recent user messages:\n\n{str_history}\n\nUser message to answer:\n\n{message}"
        system_prompt = "You are a helpful assistant. Keep the conversation with user attending to the user message. Use recent messages as context to provide better answers and adequate tone."
    else:
        formatted_prompt = message
        system_prompt = "You are a helpful assistant."

    completion = client.chat.completions.create(
        model="local-model",  # this field is currently unused
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": formatted_prompt},
        ],
        temperature=0.7,
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=completion.choices[0].message.content)


def main():
    application = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()

    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)

    message_handler = MessageHandler(None, ai_chat)
    application.add_handler(message_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
