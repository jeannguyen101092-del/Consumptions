import json
import requests
from urllib.parse import quote
from google import genai

def run_sync(gemini_key, sb_url, sb_key):
    base_sb_url = sb_url.rstrip('/')
    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json"
    }
    
    try:
        client = genai.Client(api_key=gemini_key)
        # 1. Gọi Database tải danh sách các mã hàng cũ đang bị trống dữ liệu vector
        url_fetch = f"{base_sb_url}/rest/v1/thong_so_techpack?sketch_vector=is.null&select=StyleName,SketchURL"
        res = requests.get(url_fetch, headers=headers)

        if res.status_code == 200:
            warehouse_data = res.json()
            success_count = 0
            
            for row in warehouse_data:
                style_name = row.get("StyleName")
                sketch_url = row.get("SketchURL")
                
                if sketch_url and sketch_url.startswith("http"):
                    try:
                        # 2. Tải trực tiếp nội dung file ảnh cũ từ kho lưu trữ về
                        img_res = requests.get(sketch_url, timeout=5)
                        if img_res.status_code == 200:
                            # 3. Số hóa bức ảnh cũ thành mảng số 768 chiều bằng Gemini
                            embedding_res = client.models.embed_content(
                                model='text-embedding-004',
                                contents=genai.types.Part.from_bytes(data=img_res.content, mime_type='image/jpeg')
                            )
                            vector_str = json.dumps(embedding_res.embeddings.values)
                            
                            # 4. Nạp ngược chuỗi số toán học này vào cột sketch_vector
                            url_update = f"{base_sb_url}/rest/v1/thong_so_techpack?StyleName=eq.{quote(style_name)}"
                            requests.patch(url_update, json={"sketch_vector": vector_str}, headers=headers)
                            success_count += 1
                    except Exception:
                        pass
            return f"🎉 Thành công! Đã số hóa Vector {success_count} mã hàng cũ."
        return "❌ Lỗi: Không thể lấy danh sách dữ liệu từ Supabase."
    except Exception as e:
        return f"🛑 Lỗi hệ thống: {str(e)}"
