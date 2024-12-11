"""安倍晋三読み上げBOT

token.txt にDiscordで発行されたトークンを記述して下さい。
replace.csv に "正規表現","置換ワード" の文字列置換ルールを記述して下さい。
ボイスチャンネルに入室し !abe で読み上げを開始します。
!yamagami でボイスチャンネルからBOTが切断します(任意のチャンネルから行えます)
"""
import os
import sys
import re
import csv
import asyncio
from logging import (
    getLogger,
    DEBUG,
    Formatter,
    StreamHandler
)
from pathlib import Path
import librosa
import numpy as np
import torch
from style_bert_vits2.nlp import bert_models
from style_bert_vits2.constants import Languages
from style_bert_vits2.tts_model import TTSModel
from huggingface_hub import hf_hub_download
import discord
from discord.ext import commands

# loggerの作成
logger = getLogger("discordbot.py")
logger.setLevel(DEBUG)
log_handler = StreamHandler()
dt_fmt = '%Y-%m-%d %H:%M:%S'
log_formatter = Formatter('{asctime} {levelname:<8} {name} {message}', dt_fmt, style='{')
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
logger.info("logging begin.")

# Discordクライアントの作成
intents = discord.Intents.none()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(intents=intents, command_prefix="!")

# BERTモデルをダウンロード
bert_models.load_model(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")
bert_models.load_tokenizer(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")

# Hugging Faceからモデルをダウンロード
model_file = "AbeShinzo20240210_e300_s43800.safetensors"
config_file = "config.json"
style_file = "style_vectors.npy"

for file in [model_file, config_file, style_file]:
    logger.info(f"loading {file}")
    hf_hub_download("AbeShinzo0708/AbeShinzo_Style_Bert_VITS2", file, local_dir="model_assets")

# Text to Speach モデルの構築
assets_root = Path("model_assets")

model = TTSModel(
    model_path = assets_root / model_file,
    config_path = assets_root / config_file,
    style_vec_path = assets_root / style_file,
    #device = "cuda" if torch.cuda.is_available() else "cpu",
    device = "cpu",
)

# 正規表現での文字列置換ルールを読み込む
replace_rule = []
logger.info(f"loading replace.csv")
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

class InferenceStream(discord.AudioSource):
    """推論を行いストリーミングを行う
    """
    text: str = ""
    streaming : bool = False
    sr: int = 48000
    pcm: bytearray = bytearray()
    pos: int = 0

    def __init__(self, text: str):
        """constructor

        Args:
            self : ConvertNumberToDiscordPCM
            text : inference text.
        """
        super().__init__()
        self.text = text

    def inference(self) -> None:
        # inference.
        self.text = replace_words(self.text)
        sr, audio = model.infer(text=self.text)
        self.pos = 0
        fpmono = np.zeros(len(audio))
        # convert 16bit integer to floating point for librosa.
        for i in range(len(audio)):
            fpmono[i] = (float(audio[i]) / 32767.0)
        # resampling
        resampled = librosa.resample(
            y = fpmono,
            orig_sr = sr,
            target_sr = self.sr,
            res_type = "soxr_hq" 
        )
        # normalize signal.
        resampled = librosa.util.normalize(resampled)
        # pack signal into bytearray.
        self.pcm = bytearray(len(resampled) * 2 * 2)
        for i in range(len(resampled)):
            sample = int(32767 * resampled[i])
            if sys.byteorder == "little":
                # pack into little endian 16bit stereo samples.
                self.pcm[i * 4 + 0] = (sample >> 0) & 0xFF
                self.pcm[i * 4 + 1] = (sample >> 8) & 0xFF
                self.pcm[i * 4 + 2] = (sample >> 0) & 0xFF
                self.pcm[i * 4 + 3] = (sample >> 8) & 0xFF
            else:
                # pack into big endian 16bit stereo samples.
                self.pcm[i * 4 + 0] = (sample >> 8) & 0xFF
                self.pcm[i * 4 + 1] = (sample >> 0) & 0xFF
                self.pcm[i * 4 + 2] = (sample >> 8) & 0xFF
                self.pcm[i * 4 + 3] = (sample >> 0) & 0xFF

    def read(self) -> bytes:
        """tgt_sr * 20ms分のRAWステレオPCMを返し次のオフセットを記憶します

        Returns
            bytearray
                切り出したRAWステレオPCMデータ
        """
        # inference
        if not self.streaming:
            self.inference()
            self.streaming = True

        # streaming.
        rem = len(self.pcm) - self.pos
        pad = 0
        if rem == 0:
            return bytes(0)
        frame_size = int(self.sr * 0.02 * 2 * 2) # sampling_rate * 20ms * 2(stereo) * 2(16bits)
        req = frame_size
        if req > rem:
            pad = frame_size - rem
            req = rem
        slice = self.pcm[self.pos:self.pos + req]
        self.pos = self.pos + req
        return bytes(slice + bytes(pad))

    def is_opus(self) -> bool:
        """PCMなので常に False を返します

        Returns
            bool
                常に False
        """
        return False

    def cleanup(self) -> None:
        """クリーンアップが必要な時に呼ばれます
        """
        self.text = ""
        self.streaming = False
        self.pcm = bytearray(0)
        self.pos = 0
        self.sr = 0


@bot.event
async def on_ready() -> None:
    """Discordへ接続した時に呼ばれます
    """
    logger.info(f"Logged in as")
    logger.info(f"client.user.name: {bot.user.name}")
    logger.info(f"client.user.id: {bot.user.id}")
    logger.info(f"discord.version: {discord.__version__}")
    logger.info(f'ready...')

# 接続中チャンネルID一覧
connected_channels = []

@bot.event
async def on_disconnect():
    logger.info("disconnect from peer.")
    connected_channels.clear()

@bot.command(name="abe", description="安倍晋三読み上げBOTを接続します")
async def connect(ctx: discord.Interaction) -> None:
    """!abe コマンドを受けた時に呼び出されます

    Args:
        ctx : discord.Interaction
    """
    logger.info("connect")
    if ctx.message.author.voice is None:
        await ctx.message.channel.send("あなたはボイスチャンネルに接続していません。")
        return
    if ctx.message.guild.voice_client:
        await ctx.message.channel.send("他のチャンネルで使用されています、切断してからお試し下さい。")
        return
    logger.info(f"connecting to channel {ctx.message.author.voice.channel.id}")
    connected_channels.append(ctx.message.author.voice.channel.id)
    await ctx.message.author.voice.channel.connect()
    await ctx.message.channel.send("接続しました、!yamagami で切断します。")

@bot.command(name="yamagami", description="安倍晋三読み上げBOTを切断します")
async def disconnect(ctx: discord.Interaction) -> None:
    """!yamagami コマンドを受けた場合に呼び出されます

    Args:
        ctx : discord.Interaction
    """
    logger.info("disconnect")
    if ctx.message.guild.voice_client is None:
        await ctx.message.channel.send("接続していません。")
        return
    # disconnect
    logger.info(f"disconnecting from channel {ctx.message.channel.id}")
    if ctx.message.channel.id in connected_channels:
        connected_channels.remove(ctx.message.channel.id)
    await ctx.message.guild.voice_client.disconnect()
    await ctx.message.channel.send("切断しました。")

@bot.event
async def on_message(message: discord.Message) -> None:
    """接続中チャンネルにメッセージが投稿される度に呼ばれます

    Args:
        message : discord.Message
    """
    # passing to bot command process.
    await bot.process_commands(message)
    # ignore bot message or connection not avilable.
    if message.author.bot or message.guild.voice_client is None:
        return
    # ignore not voice channel message.
    if message.author.voice is None:
        return
    # ignore not matching voice client and guild id.
    if message.content.startswith("!"):
        return
    if message.channel.id in connected_channels:
        logger.info(f"inference on channel {message.channel.id}")
        # ignore empty lines.
        text = message.content
        text.strip()
        if len(text) == 0:
            return
        # skip previous playing stream.
        if message.guild.voice_client.is_playing():
            logger.info("長い読み上げを省略します")
            message.guild.voice_client.stop()
            text = "省略しました。" + text
        # inference and play PCM stream.
        message.guild.voice_client.play(InferenceStream(text))

def main() -> None:
    """token.txtを読み込みDiscordとの通信を開始します
    """
    if not os.path.isfile("token.txt"):
        logger.error(f"token.txt not found.")
        logger.error(f"{os.getcwd()} に token.txt を作成して下さい")
        exit(-1)
    with open("token.txt") as f:
        token = f.read().strip()
        logger.info("Discordとの通信を開始します")
        bot.run(token)

if __name__ == '__main__':
    main()
