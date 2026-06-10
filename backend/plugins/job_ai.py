from flask import Blueprint, request, jsonify
import json
import logging
from core.dify_client import DifyClient
from core.response import success_response, error_response, parse_dify_outputs

logger = logging.getLogger(__name__)

# Dify 配置（每个智能体独立的 API Key 和 App ID）
DIFY_API_KEY = "app-3fb4da1ee9634e890279034d35b46d3b"
DIFY_API_URL = "http://127.0.0.1:8081/v1/workflows/run"
DIFY_UPLOAD_URL = "http://127.0.0.1:8081/v1/files/upload"

dify_client = DifyClient(DIFY_API_KEY, DIFY_API_URL, DIFY_UPLOAD_URL)

job_ai_bp = Blueprint('job_ai', __name__, url_prefix='/api/job_ai')

@job_ai_bp.route("/analyze", methods=["POST"])
def analyze():
    try:
        file = request.files.get("file")
        inputs = {
            "stage": "analyze",
            "job_name": request.form.get("job_name", ""),
            "industry": request.form.get("industry", ""),
            "description": request.form.get("description", ""),
            "responsibilities": request.form.get("responsibilities", "")
        }
        if file:
            inputs["file"] = dify_client.build_file_input(file.stream, file.filename, file.content_type)
        
        result = dify_client.run_workflow(inputs)
        outputs = parse_dify_outputs(result)
        if "analyze_result" in outputs:
            outputs["analyze_result"] = dify_client.clean_think_tags(outputs["analyze_result"])
        
        return jsonify(success_response(data=outputs))
    except Exception as e:
        logger.error(f"job_ai analyze 异常: {e}", exc_info=True)
        return jsonify(error_response(str(e))), 500

@job_ai_bp.route("/generate", methods=["POST"])
def generate():
    try:
        file = request.files.get("file")
        inputs = {
            "stage": "generate",
            "suggest_job": request.form.get("suggest_job", ""),
            "choose_id": request.form.get("choose_id", ""),
            "job_name": request.form.get("job_name", ""),
            "industry": request.form.get("industry", ""),
            "description": request.form.get("description", ""),
            "responsibilities": request.form.get("responsibilities", ""),
            "file_text": request.form.get("file_text", ""),
            "count": request.form.get("count", "")
        }
        if file:
            inputs["file"] = dify_client.build_file_input(file.stream, file.filename, file.content_type)
        
        result = dify_client.run_workflow(inputs)
        outputs = parse_dify_outputs(result)
        if "generate_result" in outputs:
            outputs["generate_result"] = dify_client.clean_think_tags(outputs["generate_result"])
        
        return jsonify(success_response(data=outputs))
    except Exception as e:
        logger.error(f"job_ai generate 异常: {e}", exc_info=True)
        return jsonify(error_response(str(e))), 500

@job_ai_bp.route("/confirm", methods=["POST"])
def confirm():
    try:
        body = request.get_json()
        inputs = {
            "stage": "confirm",
            "jobs_json": json.dumps(body.get("jobs", []), ensure_ascii=False)
        }
        
        result = dify_client.run_workflow(inputs)
        outputs = parse_dify_outputs(result)
        return jsonify(success_response(data=outputs))
    except Exception as e:
        logger.error(f"job_ai confirm 异常: {e}", exc_info=True)
        return jsonify(error_response(str(e))), 500
