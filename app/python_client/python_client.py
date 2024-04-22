import asyncio
import tkinter as tk
import json
import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
import os
import cv2

async def run(pc, player, offer):
    @pc.on("track")
    def on_track(track):
        print("Track received:", track.kind)

        if track.kind == "video":
            @track.on("frame")
            def on_frame(frame):
                print("Frame received")
                img = frame.to_ndarray(format="bgr24")
                cv2.imshow("Received Frame", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    cv2.destroyAllWindows()

    if offer:
        await pc.setRemoteDescription(offer)

# カメラデバイスを探索する関数（Linuxを想定）
def find_camera_device():
    # Linuxのビデオデバイスを探索
    for i in range(10):
        device_path = f"/dev/video{i}"
        if os.path.exists(device_path):
            return device_path
    raise RuntimeError("No camera device found")

# FastAPIサーバーにオファーを送信し、アンサーを受け取る関数（接続を確立する目的）
async def fetch_offer(pc):
    async with aiohttp.ClientSession() as session:
        # オファーを作成し、ローカルディスクリプションに設定
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        # オファーをFastAPIサーバーに送信し、アンサーを受け取る
        response = await session.post("http://localhost:8080/offer", json={
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
        answer = await response.json()

        # 受け取ったアンサーをリモートディスクリプションとして設定
        return RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])

# PeerConnectionを作成し、カメラからの映像を取得する関数
async def create_peer_connection(player):
    pc = RTCPeerConnection()
    pc.addTrack(player.video)

    # トラックの受信イベントを処理するリスナーを設定
    # @pc.on("track")
    # def on_track(track):
        # print("Track received:", track.kind)
        # print("OK") 

    # データチャネルを作成し、イベントリスナーを設定
    dc = pc.createDataChannel("chat")
    @dc.on("open")
    def on_open():
        print("Data channel opened")
        dc.send("Hello from Python!")

    @dc.on("message")
    def on_message(message):
        print("Received message:", message)

    return pc

# メイン関数
async def main():
    camera_device = find_camera_device()
    player = MediaPlayer(camera_device, format="v4l2")
    pc = await create_peer_connection(player)
    offer = await fetch_offer(pc)
    await run(pc, player, offer)
    # 接続を維持するための無限ループ
    try:
        # 接続が確立するまで待機します。
        await asyncio.sleep(999)
    except KeyboardInterrupt:
        pass
    finally:
        # クリーンアップ
        await pc.close()
        player.close()

if __name__ == "__main__":
    asyncio.run(main())
