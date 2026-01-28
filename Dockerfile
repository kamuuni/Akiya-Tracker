FROM python:3.11-slim

WORKDIR /app

# 必要なライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 今いる場所のファイルをすべてコンテナの中にコピー
COPY . .

# コンテナが起動しっぱなしになるようにする命令
CMD ["tail", "-f", "/dev/null"]