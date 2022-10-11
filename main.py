from fastapi import FastAPI, Query, Request, HTTPException
from typing import Union, List

from pydantic import BaseModel, Field
import markdown2
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from captcha.audio import AudioCaptcha
from captcha.image import ImageCaptcha
from slugify import slugify
from uuid import uuid4
from deta import Deta
from coolname import generate_slug
from os import getenv
import random
import io

deta = Deta()
db = deta.Base('PrivateSimpleCaptchaApi')
app = FastAPI()
API_KEY_FOUR_AUTH = getenv("API_KEY_FOUR_AUTH")


class CaptchaModel(BaseModel):
    captcha_id: str
    image_url: str
    audio_url: str
    text_of_captcha: str
    audio_captcha_numbers: int
    how_many_times_accessed: int = Field(default=0,
                                         description="this number is a counter. It is increased by every /get-captcha request.")


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def root():
    with open("README.md", "r", encoding="utf-8") as file:
        readme_content = file.read()
    return markdown2.markdown(readme_content)


@app.get('/create-captcha-from-custom-text', response_model=CaptchaModel)
def create_captcha_from_custom_text(request: Request, custom_text: str):
    captcha_id = str(uuid4())
    audio_captcha_numbers = random.randint(1001, 9998)
    host = request.headers.get("host")
    captcha = CaptchaModel(
        image_url="https://" + host + "/get-captcha-image/" + captcha_id + ".png",
        text_of_captcha=custom_text,
        audio_captcha_numbers=audio_captcha_numbers,
        audio_url="https://" + host + "/get-captcha-audio/" + captcha_id + ".wav",
        captcha_id=captcha_id,
    )
    db.put(data=captcha.__dict__, key=captcha_id, expire_in=(60 * 60 * 24))

    return captcha


@app.get('/create-random-captcha', response_model=CaptchaModel)
def create_random_captcha(request: Request,
                          number_of_words: int = Query(default=1, ge=1, description="How may words should be used?")):
    captcha_id = str(uuid4())

    if (number_of_words == 1):
        text_of_captcha = generate_slug(2).split("-")[0]
    else:
        text_of_captcha = generate_slug(number_of_words).replace("-", " ")
    audio_captcha_numbers = random.randint(1001, 9998)
    host = request.headers.get("host")
    captcha = CaptchaModel(
        image_url="https://" + host + "/get-captcha-image/" + captcha_id + ".png",
        text_of_captcha=text_of_captcha,
        audio_captcha_numbers=audio_captcha_numbers,
        audio_url="https://" + host + "/get-captcha-audio/" + captcha_id + ".wav",
        captcha_id=captcha_id,
    )

    db.put(data=captcha.__dict__, key=captcha_id, expire_in=(60 * 60 * 24))

    # drive.put("asds","sasdsadsa")
    # with open('/tmp/' + captcha_id + '.png', 'rb') as image_file:
    # drive.put(captcha_id + '.png', image_file.read())

    return captcha


@app.get('/get-captcha/{captcha_id}', response_model=CaptchaModel)
def get_captcha(captcha_id: str, api_key_for_auth: str = Query(title="Api Key which was set at the deployment",
                                                               example="7207a43b-2f02-4cf5-9338-70f6aa617260")):
    if (api_key_for_auth != API_KEY_FOUR_AUTH):
        raise HTTPException(status_code=401, detail="Api Key is wrong")
    captcha = db.get(captcha_id)
    if (captcha == None):
        raise HTTPException(status_code=404, detail="Captcha Id Not Found!")
    captcha['how_many_times_accessed']+=1
    db.put(captcha,captcha['key'])
    return captcha


@app.get('/get-captcha-image/{captcha_id}.png', response_class=StreamingResponse)
def get_captcha_image(captcha_id: str):
    captcha = db.get(captcha_id)
    if (captcha == None):
        raise HTTPException(status_code=404, detail="Captcha Id Not Found!")
    text_of_captcha = captcha['text_of_captcha']
    image = ImageCaptcha(width=600, height=200)
    return StreamingResponse(image.generate(text_of_captcha), media_type="image/png")


@app.get('/get-captcha-audio/{captcha_id}.wav', response_class=StreamingResponse)
def get_captcha_audio(captcha_id: str):
    captcha = db.get(captcha_id)
    if (captcha == None):
        raise HTTPException(status_code=404, detail="Captcha Id Not Found!")
    audio_captcha_numbers = captcha['audio_captcha_numbers']
    audio = AudioCaptcha()
    return StreamingResponse(io.BytesIO(audio.generate(str(audio_captcha_numbers))), media_type="audio/wav")
