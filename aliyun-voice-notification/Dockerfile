FROM python:3.11-slim

LABEL maintainer="n9e-voice-service"
LABEL description="夜莺 v7.7+ 语音通知 HTTP 服务"

WORKDIR /app

# 安装依赖
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# 复制脚本
COPY n9e-voice-server.py .

# 暴露端口
EXPOSE 8085

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8085/health')" || exit 1

# 启动服务
CMD ["python", "n9e-voice-server.py"]
