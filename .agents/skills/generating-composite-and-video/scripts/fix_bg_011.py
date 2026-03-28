import os
import requests
import json
import time
from pathlib import Path

# Load API keys from .env
def get_kie_token():
    env_path = Path(".env")
    if not env_path.exists():
        return os.environ.get("KIE_API_TOKEN")
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("KIE_API_TOKEN="):
                return line.strip().split("=")[1]
    return None

KIE_API_TOKEN = get_kie_token()
CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
STATUS_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

def fix_bg_004():
    if not KIE_API_TOKEN:
        print("Error: KIE_API_TOKEN not found.")
        return

    # 1. Re-generate bg_004 with Flux-2 (better text) using the old one as reference
    old_bg_004_url = "https://i.ibb.co/jvXbHN2J/59cb94745117.png"
    prompt = (
        "High-detail educational wall poster in a school art classroom, Pixar-style 3D animation. "
        "The poster has three clear vertical sections. "
        "Left section: 'SCULPTURE' title, 'ĐIÊU KHẮC' subtitle, illustration of a sculptor at work. "
        "Middle section: 'FASHION DESIGN' title, 'THIẾT KẾ THỜI TRANG' subtitle, illustration of a fashion designer. "
        "Right section: 'PAINTING' title, 'HỘI HỌA' subtitle, illustration of a painter at an easel. "
        "Bright rainbow border around the whole poster. Sharp, readable text. Natural classroom morning lighting, high detail rendering, no characters."
    )
    
    payload = {
        "model": "flux-2/pro-image-to-image",
        "input": {
            "input_urls": [old_bg_004_url],
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "resolution": "1K"
        }
    }
    
    headers = {"Authorization": f"Bearer {KIE_API_TOKEN}", "Content-Type": "application/json"}
    
    print("Submitting flux-2 job for bg_004 (High quality text)...")
    resp = requests.post(CREATE_URL, headers=headers, json=payload, timeout=30)
    print(f"Response Status: {resp.status_code}")
    print(f"Response Text: {resp.text}")
    
    try:
        data = resp.json()
        if data.get("code") != 200:
            print(f"API Error: {data.get('msg')}")
            return None
        task_id = data["data"]["taskId"]
    except Exception as e:
        print(f"Failed to parse JSON or find taskId: {e}")
        return None
        
    print(f"Task ID: {task_id}")
    
    # Poll for result
    while True:
        status_resp = requests.get(STATUS_URL, headers=headers, params={"taskId": task_id}, timeout=30)
        data = status_resp.json()["data"]
        state = data.get("state", "").lower()
        if state == "success":
            result_json = data.get("resultJson")
            if isinstance(result_json, str):
                result_json = json.loads(result_json)
            result_url = result_json["resultUrls"][0]
            print(f"Success! New bg_004 URL: {result_url}")
            return result_url
        elif state == "fail":
            print(f"Failed: {data.get('failMsg', 'Unknown error')}")
            return None
        print(f"Polling state: {state}...")
        time.sleep(10)

def main():
    new_url = fix_bg_004()
    if new_url:
        print("\nACTION REQUIRED:")
        print("1. Update 'image_url' for bg_004 in backgrounds.json")
        print("2. Delete 'composites/shot_011.png' and 'clips/shot_011.mp4'")
        print("3. Re-run generate_videos.py --shot shot_011")

if __name__ == "__main__":
    main()
