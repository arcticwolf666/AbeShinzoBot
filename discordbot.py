"""安倍晋三読み上げBOT

token.txt にDiscordで発行されたトークンを記述して下さい。
replace.csv に "正規表現","置換ワード" の文字列置換ルールを記述して下さい。
"""
import os
import re
import csv
from pathlib import Path
from scipy.io import wavfile
import torch
from style_bert_vits2.nlp import bert_models
from style_bert_vits2.constants import Languages
from style_bert_vits2.tts_model import TTSModel
from huggingface_hub import hf_hub_download
import discord

# Discordクライアントの作成
intents = discord.Intents.none()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
client = discord.Client(intents=intents)

# BERTモデルをダウンロード
bert_models.load_model(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")
bert_models.load_tokenizer(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")

# Hugging Faceからモデルをダウンロード
model_file = "AbeShinzo20240210_e300_s43800.safetensors"
config_file = "config.json"
style_file = "style_vectors.npy"

for file in [model_file, config_file, style_file]:
    print(file)
    hf_hub_download("AbeShinzo0708/AbeShinzo_Style_Bert_VITS2", file, local_dir="model_assets")

# Text to Speach モデルの構築
assets_root = Path("model_assets")

model = TTSModel(
    model_path = assets_root / model_file,
    config_path = assets_root / config_file,
    style_vec_path = assets_root / style_file,
    device="cuda" if torch.cuda.is_available else "cpu",
)

# 正規表現での文字列置換ルールを読み込む
replace_rule = []
with open("replace.csv", "r", encoding="utf-8") as csv_file:
    rules = csv.reader(
        csv_file,
        delimiter=",",
        doublequote=True,
        lineterminator="\r\n",
        quotechar='"',
        skipinitialspace=True
    )
    for line in rules:
        replace_rule.append((line[0], line[1]))

def replace_words(text: str) -> str:
    """replace.csvで定義した文字列置換ルールを適用します
    Args:
        text:
            入力テキストを指定します
    Returns:
        文字列置換ルールを適用したテキストを返します
    """
    for regex, replace in replace_rule:
        text = re.sub(regex, replace, text)
    return text

@client.event
async def on_ready() -> None:
    """Discordへ接続した時に呼ばれます
    """
    print(f"Logged in as")
    print(f"client.user.name: {client.user.name}")
    print(f"client.user.id: {client.user.id}")
    print(f"discord.version: {discord.__version__}")
    print(f'ready...')

@client.event
async def on_message(message) -> None:
    """Discordのチャンネルでメッセージが送られた場合に呼ばれます
    Args:
        message:
            https://discordpy.readthedocs.io/ja/latest/api.html#messages
    """
    if message.author.bot:
        return
    if message.content == "/join abe":
        if message.author.voice is None:
            await message.channel.send("あなたはボイスチャンネルに接続していません。")
            return
        # connect to voice channel
        await message.author.voice.channel.connect()
        await message.channel.send("接続しました。")
    elif message.content == "/leave abe":
        if message.guild.voice_client is None:
            await message.channel.send("接続していません。")
            return
        # disconnect
        await message.guild.voice_client.disconnect()
        await message.channel.send("切断しました。")
    else:
        if message.guild.voice_client is None:
            await message.channel.send("切断されました、再度接続して下さい。")
            return
        # inference and play local wav file.
        text = replace_words(message.content)
        sr, audio = model.infer(text=text)
        filename="output.wav"
        wavfile.write(filename, sr, audio)
        message.guild.voice_client.play(discord.FFmpegPCMAudio(filename))

def main() -> None:
    """token.txtを読み込みDiscordとの通信を開始します
    """
    if not os.path.isfile("token.txt"):
        print(f"token.txt が存在しません")
        print(f"{os.getcwd()} に token.txt を作成して下さい")
        exit(-1)
    with open("token.txt") as f:
        token = f.read()
        token = token.strip()
        print("Discordとの通信を開始します Ctrl+C で終了します")
        client.run(token)

if __name__ == '__main__':
    main()