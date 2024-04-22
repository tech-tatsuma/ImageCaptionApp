from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration, MarianMTModel, MarianTokenizer
from PIL import Image
import io

# fastapiのインスタンス化
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Reactアプリが稼働しているURL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 画像のキャプション生成モデルの初期化
device = torch.device('cpu')
processor = BlipProcessor.from_pretrained("noamrot/FuseCap")
model = BlipForConditionalGeneration.from_pretrained("noamrot/FuseCap").to(device)

# 画像データをPIL.Imageオブジェクトに変換する関数
def load_image_from_bytes(image_bytes):
    image_stream = io.BytesIO(image_bytes)
    image = Image.open(image_stream).convert("RGB")
    return image

# キャプションを生成する関数
def inference(raw_image):
    image = load_image_from_bytes(raw_image)
    text = "a picture of "
    inputs = processor(image, text, return_tensors="pt").to(device)
    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    caption_clean = caption.replace("a picture of", "").strip()
    return caption_clean

@app.post("/gencap/en")
async def generate_caption_en(file: UploadFile = File(...)):
    # 画像データを読み込む
    image_bytes = await file.read()
    # キャプション生成
    caption = inference(image_bytes)
    # キャプションを返す
    return {"caption": caption}