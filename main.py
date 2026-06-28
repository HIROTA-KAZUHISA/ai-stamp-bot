import os
import base64
from flask import Flask, request, abort, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageSendMessage, TextSendMessage
import google.generativeai as genai
import io
import uuid

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
BASE_URL = os.environ.get("BASE_URL")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)

image_store = {}


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
            return base64.b64decode(part.inline_data.data)
    return None


@app.route("/images/<image_id>")
def serve_image(image_id):
    if image_id in image_store:
        return send_file(
            io.BytesIO(image_store[image_id]),
            mimetype="image/png",
        )
    abort(404)


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
        image_id = str(uuid.uuid4())
        image_store[image_id] = image_data
        image_url = f"{BASE_URL}/images/{image_id}"
        line_bot_api.reply_message(
            event.reply_token,
            ImageSendMessage(
                original_content_url=image_url,
                preview_image_url=image_url,
            ),
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="画像生成に失敗しました。もう一度試してください。"),
        )


@app.route("/")
def index():
    return "AI STAMP Bot is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
