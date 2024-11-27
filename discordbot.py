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
import time
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
    print(file)
    hf_hub_download("AbeShinzo0708/AbeShinzo_Style_Bert_VITS2", file, local_dir="model_assets")

# Text to Speach モデルの構築
assets_root = Path("model_assets")

model = TTSModel(
    model_path = assets_root / model_file,
    config_path = assets_root / config_file,
    style_vec_path = assets_root / style_file,
    device = "cuda" if torch.cuda.is_available else "cpu",
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

class ConvertMonoToDiscordPCM(discord.AudioSource):
    """numpy.ndarrayのモノラルPCMを16bitステレオPCMに変換するストリーム
    """
    pcm:bytearray = bytearray()
    pos:int = 0
    sr:int = 0

    def __init__(self,
                 mono: np.ndarray,
                 org_sr: int,
                 tgt_sr: int
                 ):
        """constructor

        Args:
            self : ConvertNumberToDiscordPCM
            mono : np.ndarray
                mono pcm audio
            org_sr : int
                original sampling rate
            tgt_sr : int
                target sampling rate
        """
        super().__init__()
        self.pos = 0
        self.sr = tgt_sr
        fpmono = np.zeros(len(mono))
        # convert 16bit integer to floating point for librosa.
        for i in range(len(mono)):
            fpmono[i] = (float(mono[i]) / 32767.0)
        # resampling
        resampled = librosa.resample(
            y = fpmono,
            orig_sr = org_sr,
            target_sr = tgt_sr,
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
        self.pcm = bytearray(0)
        self.pos = 0

def inference(text: str, voice_client: discord.VoiceProtocol) -> None:
    """inference and play local wav file.

    Args:
        text:
            音声合成するテキスト
        voice_client:
            Discordのボイスクライアント
    """
    text = replace_words(text)
    sr, audio = model.infer(text=text)
    source = ConvertMonoToDiscordPCM(audio, sr, 48000)
    voice_client.play(source)

@bot.event
async def on_ready() -> None:
    """Discordへ接続した時に呼ばれます
    """
    print(f"Logged in as")
    print(f"client.user.name: {bot.user.name}")
    print(f"client.user.id: {bot.user.id}")
    print(f"discord.version: {discord.__version__}")
    print(f'ready...')

@bot.command(name="abe", description="安倍晋三読み上げBOTを接続します")
async def connect(ctx: discord.Interaction) -> None:
    """!abe コマンドを受けた時に呼び出されます

    Args:
        ctx : discord.Interaction
    """
    print("connect")
    if ctx.message.author.voice is None:
        await ctx.message.channel.send("あなたはボイスチャンネルに接続していません。")
        return
    if ctx.message.guild.voice_client:
        await ctx.message.channel.send("他のチャンネルで使用されています、切断してからお試し下さい。")
        return
    await ctx.message.author.voice.channel.connect()
    await ctx.message.channel.send("接続しました、!yamagami で切断します。")

@bot.command(name="yamagami", description="安倍晋三読み上げBOTを切断します")
async def disconnect(ctx: discord.Interaction) -> None:
    """!yamagami コマンドを受けた場合に呼び出されます

    Args:
        ctx : discord.Interaction
    """
    print("disconnect")
    if ctx.message.guild.voice_client is None:
        await ctx.message.channel.send("接続していません。")
        return
    # disconnect
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
    # does not inference command prefix.
    if message.content.startswith("!"):
        return
    # wait for audio streaming. if it does not stop after waiting 10seconds, force stop it.
    retry = 0
    retry_max = 10
    while message.guild.voice_client.is_playing():
        time.sleep(1)
        retry = retry + 1
        if retry == retry_max:
            print("再生が終らないので省略します")
            message.guild.voice_client.stop()
    # inference and play PCM stream.
    text = ("省略しました。" if retry >= retry_max else "") + message.content
    inference(text, message.guild.voice_client)

def main() -> None:
    """token.txtを読み込みDiscordとの通信を開始します
    """
    if not os.path.isfile("token.txt"):
        print(f"token.txt が存在しません")
        print(f"{os.getcwd()} に token.txt を作成して下さい")
        exit(-1)
    with open("token.txt") as f:
        token = f.read().strip()
        print("Discordとの通信を開始します Ctrl+C で終了します")
        bot.run(token)

if __name__ == '__main__':
    main()