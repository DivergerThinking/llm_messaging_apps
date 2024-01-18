import logging
import os
from collections import defaultdict
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Response
from openai import OpenAI

load_dotenv()

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Point to the local server
client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

# This dictionaty stores the messages. The key is the chat_id and the value is a list of messages.
chat_history = defaultdict(list)

app = FastAPI()


async def update_and_get_chat_history(message: str, chat_id: int, top_k_messages: int = 5) -> list:
    chat_history[chat_id].append(message)
    return chat_history[chat_id][-top_k_messages:-1]


async def ai_chat(body: dict, with_context: bool = True):
    chat_id = body["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]

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
    return completion.choices[0].message.content


async def handle_whatsapp_message(body):
    bot_response = await ai_chat(body)
    headers = {"Authorization": "Bearer " + os.environ["WHATSAPP_TOKEN"]}
    url = f"https://graph.facebook.com/v18.0/{os.environ['TEST_PHONE_ID']}/messages"
    response = {
        "messaging_product": "whatsapp",
        "to": body["entry"][0]["changes"][0]["value"]["messages"][0]["from"],
        "type": "text",
        "text": {"preview_url": False, "body": bot_response},
    }
    requests.post(url=url, json=response, headers=headers)


@app.post("/webhook/")
async def receive_webhook(body: dict):
    print(body)
    try:
        # info on WhatsApp text message payload:
        # https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples#text-messages
        if body.get("object"):
            if (
                body.get("entry")
                and body["entry"][0].get("changes")
                and body["entry"][0]["changes"][0].get("value")
                and body["entry"][0]["changes"][0]["value"].get("messages")
                and body["entry"][0]["changes"][0]["value"]["messages"][0]
            ):
                await handle_whatsapp_message(body)
            return {"status": "ok"}
        else:
            # if the request is not a WhatsApp API event, return an error
            return Response(content="not a WhatsApp API event", status_code=404)

    # catch all other errors and return an internal server error
    except Exception as e:
        print(f"unknown error: {e}")
        return Response(content=str(e), status_code=500)


# Just for webhook verification
@app.get("/webhook/")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[int] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    print(hub_mode, hub_challenge, hub_verify_token)
    return hub_challenge


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("whatsapp_itor_bot:app", host="0.0.0.0", port=8000, reload=True)
