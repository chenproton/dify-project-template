def success_response(data=None, message="success"):
    return {
        "code": 200,
        "message": message,
        "data": data
    }

def error_response(message, code=500):
    return {
        "code": code,
        "message": message,
        "data": None
    }

def parse_dify_outputs(result):
    """解析 Dify 响应中的 outputs"""
    return result.get("data", {}).get("outputs", {})
