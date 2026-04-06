import json
import re
import requests
import time
from datetime import datetime, timezone

APP_ID = "cli_a958e27796f8d2cc2"
APP_SECRET = "onQGFUVKnbPRHhlwYAGHYdq8RDLnt5Dz"
APP_TOKEN = "MUtrbPOD6aZ160slmREcJgVTnRc"
TABLE_ID = "tblT22iTLfVeLgUO"

tenant_access_token = None
token_expire_at = 0

def get_tenant_access_token():
    global tenant_access_token, token_expire_at
    if tenant_access_token and time.time() < token_expire_at:
        return tenant_access_token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": APP_ID, "app_secret": APP_SECRET}
    resp = requests.post(url, headers=headers, json=data)
    data = resp.json()
    if data.get("code") == 0:
        tenant_access_token = data["tenant_access_token"]
        token_expire_at = time.time() + data["expire"] - 60
        return tenant_access_token
    raise Exception(f"获取token失败: {data}")

def add_record(uric_acid, blood_sugar, remark):
    token = get_tenant_access_token()
    now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    fields = {"日期": now_ts, "备注": remark}
    if uric_acid is not None:
        fields["尿酸（μmol/L）"] = uric_acid
    if blood_sugar is not None:
        fields["空腹血糖（mmol/L）"] = blood_sugar
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"fields": fields})
    data = resp.json()
    return data.get("code") == 0

def reply_message(message_id, content):
    token = get_tenant_access_token()
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"content": json.dumps({"text": content}, ensure_ascii=False), "msg_type": "text"}
    resp = requests.post(url, headers=headers, json=body)
    data = resp.json()
    return data.get("code") == 0

def parse_text(text):
    uric = sugar = None
    remark = text.strip()
    uric_match = re.search(r"尿酸\s*[:：]?\s*(\d+\.?\d*)", text)
    if uric_match:
        uric = float(uric_match.group(1))
        remark = remark.replace(uric_match.group(0), "").strip()
    sugar_match = re.search(r"血糖\s*[:：]?\s*(\d+\.?\d*)", text)
    if sugar_match:
        sugar = float(sugar_match.group(1))
        remark = remark.replace(sugar_match.group(0), "").strip()
    return uric, sugar, remark

def handler(request):
    try:
        body = request.get_json()
        
        # 验证 URL
        if body and body.get("type") == "url_verification":
            return {
                "challenge": body["challenge"]
            }
        
        # 处理消息
        if body and body.get("type") == "event_callback":
            event = body.get("event", {})
            if body.get("type") == "im.message.receive_v1":
                message = event.get("message", {})
                msg_id = message.get("message_id")
                if message.get("message_type") == "text":
                    content = json.loads(message.get("content", "{}"))
                    text = content.get("text", "")
                    uric, sugar, remark = parse_text(text)
                    if uric is None and sugar is None:
                        reply_message(msg_id, "❌ 格式错误，示例：尿酸420 血糖5.5")
                    else:
                        if add_record(uric, sugar, remark):
                            reply_message(msg_id, f"✅ 已录入\n尿酸：{uric}\n血糖：{sugar}")
                        else:
                            reply_message(msg_id, "❌ 写入失败")
        
        return "ok"
    except Exception as e:
        return {"error": str(e)}