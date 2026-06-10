"""
智能体插件模板
============
复制此文件并重命名，快速创建新的智能体插件。

步骤：
1. 复制：cp plugins/TEMPLATE.py plugins/xxx_ai.py
2. 修改：将模板中的 "xxx" 替换为你的智能体名称
3. 配置：修改 DIFY_API_KEY 等配置
4. 注册：在 app.py 中导入并注册 Blueprint
"""

from flask import Blueprint, request, jsonify
import json
import logging
from core.dify_client import DifyClient
from core.response import success_response, error_response, parse_dify_outputs

logger = logging.getLogger(__name__)

# ========== 配置区域（每个智能体独立配置）==========
DIFY_API_KEY = "your-api-key-here"           # 替换为你的 Dify API Key
DIFY_API_URL = "http://127.0.0.1:8081/v1/workflows/run"
DIFY_UPLOAD_URL = "http://127.0.0.1:8081/v1/files/upload"
# ==================================================

dify_client = DifyClient(DIFY_API_KEY, DIFY_API_URL, DIFY_UPLOAD_URL)

# 创建 Blueprint
# url_prefix: API 路由前缀，建议格式 /api/<smart_agent_name>
xxx_ai_bp = Blueprint('xxx_ai', __name__, url_prefix='/api/xxx_ai')

@xxx_ai_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    分析阶段 API
    接收用户输入，调用 Dify analyze 分支
    """
    try:
        file = request.files.get("file")
        
        # 组装 inputs（根据你的业务字段调整）
        inputs = {
            "stage": "analyze",
            "field1": request.form.get("field1", ""),
            "field2": request.form.get("field2", ""),
        }
        
        # 如有文件，构建文件输入
        if file:
            inputs["file"] = dify_client.build_file_input(
                file.stream, file.filename, file.content_type
            )
        
        # 调用 Dify 工作流
        result = dify_client.run_workflow(inputs)
        outputs = parse_dify_outputs(result)
        
        # 清洗输出（如去掉 think 标签）
        if "analyze_result" in outputs:
            outputs["analyze_result"] = dify_client.clean_think_tags(
                outputs["analyze_result"]
            )
        
        return jsonify(success_response(data=outputs))
    except Exception as e:
        logger.error(f"xxx_ai analyze 异常: {e}", exc_info=True)
        return jsonify(error_response(str(e))), 500


@xxx_ai_bp.route("/generate", methods=["POST"])
def generate():
    """
    生成阶段 API
    接收用户选择，调用 Dify generate 分支
    """
    try:
        file = request.files.get("file")
        
        inputs = {
            "stage": "generate",
            "selected_items": request.form.get("selected_items", ""),
            "count": request.form.get("count", ""),
            # 添加其他字段...
        }
        
        if file:
            inputs["file"] = dify_client.build_file_input(
                file.stream, file.filename, file.content_type
            )
        
        result = dify_client.run_workflow(inputs)
        outputs = parse_dify_outputs(result)
        
        if "generate_result" in outputs:
            outputs["generate_result"] = dify_client.clean_think_tags(
                outputs["generate_result"]
            )
        
        return jsonify(success_response(data=outputs))
    except Exception as e:
        logger.error(f"xxx_ai generate 异常: {e}", exc_info=True)
        return jsonify(error_response(str(e))), 500


@xxx_ai_bp.route("/confirm", methods=["POST"])
def confirm():
    """
    确认阶段 API
    接收最终结果，调用 Dify confirm 分支
    """
    try:
        body = request.get_json()
        
        inputs = {
            "stage": "confirm",
            "data_json": json.dumps(body.get("data", []), ensure_ascii=False)
        }
        
        result = dify_client.run_workflow(inputs)
        outputs = parse_dify_outputs(result)
        
        return jsonify(success_response(data=outputs))
    except Exception as e:
        logger.error(f"xxx_ai confirm 异常: {e}", exc_info=True)
        return jsonify(error_response(str(e))), 500
