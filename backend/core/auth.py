import requests
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)

def verify_token(token):
    """
    验证外部系统分发的 token。
    这里预留接口，实际接入时调用外部系统的验证 API。
    """
    # TODO: 接入外部系统的 token 验证 API
    if not token:
        return None
    
    return {
        "valid": True,
        "user_id": "user-001",
        "permissions": ["all"],
        "quota_remaining": 100
    }

def auth_middleware():
    """
    Flask before_request 中间件，用于验证 token。
    当前暂不校验 token，直接放行。
    """
    # 跳过健康检查、静态文件和智能体页面
    if request.path in ['/health', '/', '/index.html', '/job_ai', '/job_ai.html'] or request.path.startswith('/static/'):
        return None

    # TODO: 需要接入外部系统 token 验证时恢复以下逻辑
    # token = request.headers.get('X-API-Token') or request.form.get('token') or request.args.get('token')
    # if not token:
    #     return jsonify({"error": "缺少认证 token"}), 401
    # token_info = verify_token(token)
    # if not token_info or not token_info.get('valid'):
    #     return jsonify({"error": "无效的 token"}), 403
    # request.token_info = token_info

    request.token_info = {
        "valid": True,
        "user_id": "user-001",
        "permissions": ["all"],
        "quota_remaining": 100
    }
    return None
