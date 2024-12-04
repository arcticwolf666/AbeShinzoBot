# AI晋さんDiscord読み上げボット

Discordのチャンネルに常駐し、投稿されたテキストを読み上げます。

## 使用モデルについて

晋バルサン氏の公開しているStyle-Bert-VITS2用のモデルをダウンロードし使用しています。<br>
https://huggingface.co/AbeShinzo0708/AbeShinzo_Style_Bert_VITS2

## 使用方法
1. Pythonの仮想環境を作成し、その中に必須パッケージをインストールします。動作確認したPythonのバージョンは3.10系です、異るバージョンがインストールされている場合、下部の補足を参考にPythonをソースからビルドして下さい。

    Windows
    ```bat
    git clone https://github.com/arcticwolf666/AbeShinzoBot
    cd AbeShinzoBot
    python -m venv venv
    venv\Scripts\activate
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    pip install -r requirements.txt
    ```

    Linux(Ubuntu-22.04) CUDA
    ```bash
    git clone https://github.com/arcticwolf666/AbeShinzoBot
    cd AbeShinzoBot
    python -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    pip install -r requirements.txt
    sudo apt-get install libopus0
    ```

    CPUでも実用的な時間で音声合成できますが、CUDAを使用する事もできます。<br>
    CUDAが使用できない環境下ではCPUにフォールバックします。<br>
    CUDAを使用する場合CUDA Toolkit 11.8をインストールして下さい。<br>
    https://developer.nvidia.com/cuda-11-8-0-download-archive

    Linux(Ubuntu-22.04) CPU
    ```bash
    git clone https://github.com/arcticwolf666/AbeShinzoBot
    cd AbeShinzoBot
    python -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    pip install -r requirements.txt
    sudo apt-get install libopus0
    ```

    CUDA向けのpytorchで上手く動作しない場合 cpu 版のtorchをインストールして下さい。<br>

2. Discord上アプリケーションを作成する

    https://discord.com/developers/applications からアプリケーションを作成する。
    ![1-application.png](images/1-applications.png)
    ![2-create.png](images/2-create.png)
    ![3-generalinfo.png](images/3-generalinfo.png)
    BOTを作成します、ResetTokenで新たなトークンが生成されるので token.txt にそれを記述します。
    ![4-createbot.png](images/4-createbot.png)
    BOTをサーバに追加する為のURLを取得します(GENERATED URL)
    ![5-oauth.png](images/5-oauth.png)
    ![6-permission.png](images/6-permission.png)
    BOTをサーバに追加する、前のGENERATED URLをブラウザで開きサーバにBOTを追加します。
    ![7-addbot.png](images/7-addbot.png)
    ![8-auth.png](images/8-auth.png)

3. token.txtを作成しDiscordで発行されたBOTのトークンを張り付け保存します。

4. Pythonの仮想環境上でBOTを動かす

    Windows
    ```
    venv\Scripts\activate
    python discordbot.py
    ```

    Linux(Ubuntu-22.04)
    ```
    source venv/Scripts/activate
    python discordbot.py
    ```

    Ctrl+Cで終了します。

5. 読み上げる

    Discordのチャンネルで !abe とコマンドを打つと、そのチャンネルに読み上げBOTが接続します。<br>
    以後テキストが読み上げられる筈です。<br>
    BOTの接続を解除するには !yamagami とコマンドを打って下さい。<br>

6. 正規表現で特定のワードを書き換える

    replace.csv に "正規表現","置換後文字列" を記述する事で特定の単語を置き換える事ができます。
    BOTがうまく読まない単語を、ひらがなで記述する事で一応読み上げる様になります。

## 補足
* Linux(Ubuntu-22.04) 上で Python-3.10.15 をビルドする

    依存パッケージをインストールする
    ```bash
    sudo apt install -y build-essential libbz2-dev libdb-dev \
        libreadline-dev libffi-dev libgdbm-dev liblzma-dev \
        libncursesw5-dev libsqlite3-dev libssl-dev \
        zlib1g-dev uuid-dev tk-dev
    ```

    Pythonをビルドする(--prefixと make -j 32 は使用環境に合せて下さい)
    ```bash
    mkdir ~/sources
    cd ~/sources
    wget https://www.python.org/ftp/python/3.10.15/Python-3.10.15.tar.xz
    tar xJfv ~/sources/Python-3.10.15.tar.xz
    cd Python-3.10.15
    ./configure --prefix=/home/owner/python3
    make -j 32
    make install
    pushd ~/python3/bin
    ln -fs python3 python
    ln -fs pip3 pip
    popd
    ```

    インストールしたPythonのビルドを有効にするするスクリプトを ~/python3/enable に作成する(/home/owner は使用環境に合せて下さい)
    ```bash
    #!/bin/bash
    PATH="/home/owner/python3/bin:$PATH"
    export PATH
    LD_LIBRARY_PATH="/home/owner/python3/lib:$LD_LIBRARY_PATH"
    export LD_LIBRARY_PATH
    hash -r
    ```

    eanbleを取り込みパスを通す
    ```bash
    source ~/python3/enable
    which python
    ```

    /home/owner/python3/bin/python が出力されていればパスが通っています。

* Linux 上で systemd のサービスとして登録する

    abeshinzobot.service の ExecStart WorkingDirecotry User を環境に合せて書き換えて下さい。

    | 名称      | 説明 |
    |-----------|------|
    | ExecStart | AbeShinzoBotに付属の run.sh の絶対パスを指定します。|
    | WorkingDirecotry | AbeShinzoBotの絶対パスを指定します。|
    | User | BOTを動かすUNIXユーザー名を指定します。|

    次のコマンドラインで systemd に登録しBOTを起動します。
    ```bash
    sudo install -g root -o root -m 644 abeshinzobot.service /etc/systemd/system/abeshinzo.service 
    sudo systemctl enable abeshinzobot
    sudo systemctl start abeshinzobot
    ```

* Linux 上で logrotate を行う

    abeshinzobot.logrotate のログファイルパスを書き換えて下さい。

    次のコマンドラインで logorate.d に設定します
    ```bash
    sudo install -g root -o root -m 644 abeshinzobot.logrotate /etc/logrotate.d/abeshinzobot
    sudo systemctl restart logrotate
    ```
