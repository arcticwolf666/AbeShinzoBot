import discord
import re
from scipy.io import wavfile

# Discordから発行されたBOTのトークンを指定
TOKEN="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
TEMPWAVFILE="output.wav"

intents = discord.Intents.none()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
client = discord.Client(intents=intents)

# BERTモデルをダウンロード
from style_bert_vits2.nlp import bert_models
from style_bert_vits2.constants import Languages

bert_models.load_model(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")
bert_models.load_tokenizer(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")

# Hugging Faceからモデルをダウンロード
from pathlib import Path
from huggingface_hub import hf_hub_download

model_file = "AbeShinzo20240210_e300_s43800.safetensors"
config_file = "config.json"
style_file = "style_vectors.npy"

for file in [model_file, config_file, style_file]:
    print(file)
    hf_hub_download("AbeShinzo0708/AbeShinzo_Style_Bert_VITS2", file, local_dir="model_assets")

# 上でダウンロードしたモデルファイルを指定して音声合成のテスト
from style_bert_vits2.tts_model import TTSModel

assets_root = Path("model_assets")

model = TTSModel(
    model_path=assets_root / model_file,
    config_path=assets_root / config_file,
    style_vec_path=assets_root / style_file,
    device="cpu",
)

def escape_words(text: str) -> str:
    return re.sub("https?://[\w!\?/\+\-_~=;\.,\*&@#\$%\(\)'\[\]]+", "リンク", text) 

@client.event
async def on_ready():
    print(f"Logged in as")
    print(f"client.user.name: {client.user.name}")
    print(f"client.user.id: {client.user.id}")
    print(f"discord.version: {discord.__version__}")
    print(f'ready...')

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content == "/join":
        if message.author.voice is None:
            await message.channel.send("あなたはボイスチャンネルに接続していません。")
            return
        # connect to voice channel
        await message.author.voice.channel.connect()
        await message.channel.send("接続しました")
    elif message.content == "/leave":
        if message.guild.voice_client is None:
            await message.channel.send("接続していません。")
            return
        # disconnect
        await message.guild.voice_client.disconnect()
        await message.channel.send("切断しました。")
    else:
        # play local wav file.
        print(f"推論します: {message.content}")
        text = escape_words(message.content)
        sr, audio = model.infer(text=text)
        wavfile.write(TEMPWAVFILE, sr, audio)
        message.guild.voice_client.play(discord.FFmpegPCMAudio(TEMPWAVFILE))

client.run(TOKEN)