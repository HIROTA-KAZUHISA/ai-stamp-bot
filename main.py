import os
import json
import base64
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageSendMessage
import google.generativeai as genai
from PIL import Image
import io

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)


def generate_stamp_image(text):
    model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")
    prompt = (
        f"Create a cute LINE sticker style image with the Japanese text '{text}'. "
        "The image should have a white background, bold colorful text in the center, "
        "with cute kawaii style decorations around it like stars, hearts, or sparkles. "
        "Make it look like a fun chat sticker. Simple, clear, and expressive."
    )
    response = model.generate_content(
        prompt,
        generation_config={"response_modalities": ["IMAGE"]},
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            image_data = base64.b64decode(part.inline_data.data)
            return image_data
    return None


def upload_image_to_imgur(image_data):
    headers = {"Authorization": "Client-ID " + os.environ.get("IMGUR_CLIENT_ID", "")}
    b64_image = base64.b64encode(image_data).decode("utf-8")
    response = requests.post(
        "https://api.imgur.com/3/image",
        headers=headers,
        data={"image": b64_image, "type": "base64"},
    )
    result = response.json()
    if result.get("success"):
        return result["data"]["link"]
    return None


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    image_data = generate_stamp_image(text)
    if image_data:
        image_url = upload_image_to_imgur(image_data)
        if image_url:
            line_bot_api.reply_message(
                event.reply_token,
                ImageSendMessage(
                    original_content_url=image_url,
                    preview_image_url=image_url,
                ),
            )
            return
    line_bot_api.reply_message(
        event.reply_token,
        TextMessage(text="画像生成に失敗しました。もう一度試してください。"),
    )


@app.route("/")
def index():
    return "AI STAMP Bot is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
