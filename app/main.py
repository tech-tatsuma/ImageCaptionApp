import asyncio
import logging
import secrets
import uuid

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRelay
from aiortc.contrib.media import MediaStreamTrack
from aiortc.contrib.media import VideoFrame
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic

from app import exception_handler
from app.my_media_transform_check import AudioTransformTrack, VideoTransformTrack
from app.settings import Settings

import numpy as np
from PIL import Image

import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
import datetime

# 画像のキャプション生成モデルの初期化
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

processor = BlipProcessor.from_pretrained("noamrot/FuseCap")
model = BlipForConditionalGeneration.from_pretrained("noamrot/FuseCap").to(device)

def inference(raw_image):
    text = "a picture of "
    inputs = processor(raw_image, text, return_tensors="pt").to(device)
    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption

# 設定とセキュリティの初期化
settings = Settings()
security = HTTPBasic()

# FastAPIの初期化
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# 例外ハンドラの登録
exception_handler.init_app(app)

# このアプリケーションのログ設定
root_logger = logging.getLogger("app")
root_logger.addHandler(logging.StreamHandler())
root_logger.setLevel(settings.LOG_LEVEL)

# WebRTC関連の変数の初期化
pcs = set()
dcs = set()
relay = MediaRelay()

# ルートパスへのGETリクエストの処理
@app.get("/", include_in_schema=False)
async def index(
    request: Request,
) -> JSONResponse:
    return JSONResponse({"message": "Welcome to the server"})

# ヘルスチェック用のエンドポイント
@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse({"message": "It worked!!"})

class VideoTransformTrack(MediaStreamTrack):
    """
    A video stream track that applies a transformation to frames from an underlying track.
    """

    kind = "video"

    def __init__(self, track, transform):
        super().__init__()  # don't forget this!
        self.track = track
        self.last_caption_time = datetime.datetime.now()

    async def recv(self):
        frame = await self.track.recv()

        current_time = datetime.datetime.now()
        if (current_time - self.last_caption_time).total_seconds() >= 5:
            self.last_caption_time = current_time
            # Convert frame to an image and generate a caption
            img_array = frame.to_ndarray(format="bgr24")
            pil_image = Image.fromarray(img_array)
            caption = inference(pil_image)
            print(f"Generated Caption: {caption}")
            if self.channel:
                self.channel.send(caption)

        return frame


@app.get("/offer", include_in_schema=False)
@app.post("/offer", include_in_schema=False)
async def offer(request: Request):
    """WebRTCのオファーを受け取り、アンサーを生成して返すAPI
    """
    # リクエストからJSONデータを取得する
    params = await request.json()
    
    # RTCSessionDescriptionを作成し、受け取ったSDP情報を設定する
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # RTCPeerConnectionのインスタンスを作成する
    pc = RTCPeerConnection()
    pc_id = "PeerConnection(%s)" % uuid.uuid4()
    pcs.add(pc)

    # Create a new data channel for sending captions
    channel = pc.createDataChannel("captionChannel")
    dcs.add(channel)

    def log_info(msg, *args):
        """データチャネルのメッセージを処理する
        """
        root_logger.info(pc_id + " " + msg, *args)

    # player = MediaPlayer("/usr/src/app/app/demo-instruct.wav")
    recorder = MediaBlackhole()

    # メディアトラックとデータチャネルの処理
    @pc.on("datachannel")
    def on_datachannel(channel):
        """データチャネルが開設された際の処理
        """
        # データチャネルをセットに追加する
        dcs.add(channel)

        @channel.on("message")
        def on_message(message):
            """データチャネルからのメッセージを受信した際の処理
            """
            # 受信したメッセージがpingで始まる場合、pongを返す
            if isinstance(message, str) and message.startswith("ping"):
                channel.send("pong" + message[4:])

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        """接続状態が変わった際の処理
        """
        # 接続状態をログに記録する
        log_info("Connection state is %s", pc.connectionState)
        # 接続状態が失敗("failed")になった場合、PeerConnectionを閉じる
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        """ メディアトラックを受信した際の処理
        """
        # 受信したトラックの種類をログに記録する
        log_info("Track {} received".format(track.kind))

        if track.kind == "video":
            # Ensure there is at least one data channel to send captions
            if dcs:  # Check if any data channel exists
                pc.addTrack(VideoTransformTrack(relay.subscribe(track), next(iter(dcs))))
            else:
                pc.addTrack(VideoTransformTrack(relay.subscribe(track), None))

        @track.on("ended")
        async def on_ended():
            # トラックが終了した際の処理
            # トラックの終了をログに記録する
            log_info("Track %s ended", track.kind)
            # レコーダーを停止する
            await recorder.stop()

    # オファーをリモートディスクリプションとして設定する
    await pc.setRemoteDescription(offer)
    # レコーダーを開始する
    await recorder.start()

    # アンサーを作成し、ローカルディスクリプションとして設定する
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # アンサーをJSONレスポンスとして返す
    return JSONResponse(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
    )


@app.post("/message", include_in_schema=False)
async def message(request: Request):
    """データチャネルを通じてメッセージを送信するAPI
    """
    # リクエストからJSONデータを取得する
    params = await request.json()
    # 全てのデータチャネルにメッセージを送信する
    [dc.send(params["message"]) for dc in dcs]


@app.on_event("shutdown")
async def on_shutdown():
    """アプリケーションのシャットダウン時に実行される処理
    """
    # 全てのピアコネクションを閉じるためのコルーチンを生成する
    coros = [pc.close() for pc in pcs]

    # 生成されたコルーチンを並行して実行する
    await asyncio.gather(*coros)
    # ピアコネクションのセットをクリアする
    pcs.clear()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
