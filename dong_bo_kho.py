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
        
        # SỬA ĐỔI QUYẾT ĐỊNH: Tải toàn bộ danh sách mã hàng không lọc NULL nữa để ép ghi đè dữ liệu số chuẩn
        url_fetch = f"{base_sb_url}/rest/v1/thong_so_techpack?select=StyleName,SketchURL"
        res = requests.get(url_fetch, headers=headers)

        if res.status_code == 200:
            warehouse_data = res.json()
            success_count = 0
            
            for row in warehouse_data:
                style_name = row.get("StyleName")
                sketch_url = row.get("SketchURL")
                
                if sketch_url and sketch_url.startswith("http"):
                    try:
                        img_res = requests.get(sketch_url, timeout=5)
                        if img_res.status_code == 200:
                            # Tiến hành gọi mô hình sinh chuỗi số Vector thực tế cho ảnh cũ
                            embedding_res = client.models.embed_content(
                                model='text-embedding-004',
                                contents=genai.types.Part.from_bytes(data=img_res.content, mime_type='image/jpeg')
                            )
                            vector_str = json.dumps(embedding_res.embeddings.values)
                            
                            # Ghi đè trực tiếp chuỗi số chuẩn này vào database
                            url_update = f"{base_sb_url}/rest/v1/thong_so_techpack?StyleName=eq.{quote(style_name)}"
                            requests.patch(url_update, json={"sketch_vector": vector_str}, headers=headers)
                            success_count += 1
                    except Exception:
                        pass
            return f"🎉 Thành công! Đã ép số hóa và làm sạch dữ liệu Vector cho {success_count} mã hàng cũ trong kho."
        return "❌ Lỗi: Không thể lấy danh sách dữ liệu từ Supabase."
    except Exception as e:
        return f"🛑 Lỗi hệ thống: {str(e)}"
