import requests
import json
import logging

logger = logging.getLogger(__name__)

class DifyClient:
    def __init__(self, api_key, api_url, upload_url):
        self.api_key = api_key
        self.api_url = api_url
        self.upload_url = upload_url
    
    def upload_file(self, file_stream, filename, content_type, user="user-001"):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {"file": (filename, file_stream, content_type)}
        data = {"user": user}
        resp = requests.post(self.upload_url, headers=headers, files=files, data=data, timeout=60)
        resp.raise_for_status()
        return resp.json()["id"]
    
    def build_file_input(self, file_stream, filename, content_type):
        upload_file_id = self.upload_file(file_stream, filename, content_type)
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext in ("pdf", "doc", "docx", "txt", "md"):
            file_type = "document"
        elif ext in ("jpg", "jpeg", "png", "gif", "webp", "svg"):
            file_type = "image"
        else:
            file_type = "document"
        return {
            "transfer_method": "local_file",
            "upload_file_id": upload_file_id,
            "type": file_type
        }
    
    def run_workflow(self, inputs, user="user-001", timeout=300):
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": user
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(self.api_url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                raw = resp.text[:500]
                logger.error(f"Dify API HTTP {resp.status_code}: {raw}")
                raise Exception(f"Dify API 返回 HTTP {resp.status_code}: {raw}")
            
            try:
                result = resp.json()
            except ValueError:
                raw = resp.text[:500]
                logger.error(f"Dify API 返回非 JSON: {raw}")
                raise Exception(f"Dify API 返回非 JSON 响应: {raw}")
            
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"请求 Dify API 失败: {e}")
            raise Exception(f"请求 Dify API 失败: {e}")
    
    def clean_think_tags(self, text):
        if not text:
            return text
        import re
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return text.strip()
