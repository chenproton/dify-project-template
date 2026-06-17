import sys
import os

# 将 backend 目录加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging

from core.auth import auth_middleware
from plugins.job_ai import job_ai_bp
from plugins.scene_ai import scene_ai_bp

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 注册认证中间件
app.before_request(auth_middleware)

# 注册 Blueprint（每个智能体一个）
app.register_blueprint(job_ai_bp)
app.register_blueprint(scene_ai_bp)

# 静态文件路径（frontend 在项目根目录，backend/app.py 在 backend 子目录）
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/job_ai")
def job_ai_page():
    return send_from_directory(os.path.join(FRONTEND_DIR, "plugins"), "job_ai.html")

@app.route("/scene_ai")
def scene_ai_page():
    return send_from_directory(os.path.join(FRONTEND_DIR, "plugins"), "scene_ai.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "ai-agent-platform"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
