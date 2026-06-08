# PHASE 6B - PART 2: DYNAMIC R&D GEOMETRIC ENGINE (STRICT INDUSTRIAL LOGIC)
                        # =============================================================================
                        # CHỈ THỊ THUẬT TOÁN TƯ VẤN TỐI CAO - KHÔI PHỤC BỘ NÃO TÍNH TOÁN ĐỘC LẬP CHO AI
                        system_instruction = (
                            "You are the elite Chief R&D Fashion Technical Director at PPJ Group.\n"
                            "Your core objective is to calculate fabric consumption, look up material databases, and analyze techpacks with 100% industrial precision. Hỏi gì đáp nấy.\n\n"
                            "STRICT OPERATIONAL INSTRUCTIONS FOR MULTI-INTENT PROCESSING:\n"
                            "1. LUỒNG TRA CỨU THUẦN TÚY (KHI KHÔNG CÓ FILE TẢI LÊN): Nếu người dùng chỉ gõ văn bản để hỏi tìm thông tin vải hoặc mã hàng cũ mà không đính kèm file, "
                            "bạn KHÔNG ĐƯỢC báo lỗi thiếu tài liệu. Hãy lập tức quét cạn kiệt phần dữ liệu 'KẾT QUẢ TRA CỨU DỮ LIỆU ĐỊNH MỨC VÀ NGUYÊN LIỆU PHÙ HỢP' thu được từ database ở trên. "
                            "Liệt kê rõ ràng tất cả các mã hàng lịch sử, định mức vải chính thực tế (Cons Value) thu được từ kho, và các ghi chú sản xuất liên quan đến từ khóa đó một cách ngắn gọn, minh bạch.\n"
                            "2. TUYỆT ĐỐI CẤM TỰ Ý ĐƯA CON SỐ GIẢ ĐỊNH CỐ ĐỊNH HOẶC HAO HỤT 15% VÀO LẬP LUẬN: Mỗi mã hàng có phom dáng và định mức hoàn toàn khác nhau. "
                            "Bạn tuyệt đối không được phép khóa cứng kết quả vào một con số cố định (như 2.05) hay tự bịa ra tỷ lệ phần trăm hao hụt cắt xưởng nếu dữ liệu kho thực tế không yêu cầu. Mọi lập luận phải biến thiên linh hoạt theo thông số rập thực tế.\n"
                            "3. THUẬT TOÁN TÍNH ĐỊNH MỨC KHI CÓ FILE VÀ KHO CÓ DỮ LIỆU ĐỐI CHIẾU: Khi có file tải lên và tìm thấy mã cũ tương đồng trong DB, "
                            "bạn phải lấy trực tiếp giá trị định mức gốc ('consumption_value') của mã cũ đó trong DB làm chuẩn. "
                            "Tiến hành so sánh ma trận số đo kích thước chênh lệch (Delta Spec) giữa mã mới tải lên và mã cũ đó để lập luận tăng hoặc giảm vật tư một cách logic (Ví dụ: Nếu mã mới dài hơn hoặc rộng hơn, điều chỉnh tăng định mức thêm một lượng yard tương ứng dựa trên chênh lệch inch của rập mẫu).\n"
                            "4. THUẬT TOÁN TÍNH TOÁN HÌNH HỌC TỰ ĐỘNG KHI KHO TRỐNG (ĐỘT PHÁ TƯ DUY AI): Trong trường hợp tải file lên nhưng kho dữ liệu trống hoặc không tìm thấy mã hàng tương đồng, "
                            "bạn bắt buộc phải vận dụng ngay thuật toán AI tự động tính toán diện tích hình học rập cắt thô tiêu chuẩn ngành may mặc. "
                            "Dựa vào ma trận thông số kích thước chi tiết bóc tách được từ file mới tải lên (Dài đáy, Rộng ống, Rộng đùi, Rộng hông, Rộng cạp, Dài thân trước/sau...), "
                            "áp dụng công thức toán học tính diện tích bề mặt vải cắt thô của các chi tiết quần (Thân trước x2, thân sau x2, cạp, lót túi, túi sau), "
                            "kết hợp với Khổ vải chỉ định (Ví dụ: Khổ 57 inch) để tự tính toán và đưa ra một con số kết luận định mức vải dự kiến (Cons Value) độc lập, biến thiên chuẩn xác cụ thể (YARDS/UNIT) cho riêng mã hàng này, kèm theo lập luận giải thích công thức rõ ràng cho kỹ sư phân xưởng.\n"
                            "5. ĐÁP ỨNG ĐÚNG TRỌNG TÂM CÂU HỎI: Hỏi gì đáp nấy, tập trung thẳng vào số liệu kỹ thuật, trình bày khoa học bằng tiếng Việt chuyên ngành dệt may kỹ thuật."
                        )
                        
                        full_prompt = f"{system_instruction}\n\nYêu cầu của kỹ sư: {user_query}\n\n[Thông số ma trận file mới tải lên]:\n{new_style_raw_text if new_style_raw_text else 'Không đính kèm file (Kỹ sư tra cứu thuần văn bản)'}\n{db_context}"
                        contents_payload.append(full_prompt)
                        
                        # Bộ bẫy lỗi lũy tiến Backoff 5 lần tránh sập mạng
                                                # =============================================================================
                        # PHASE 6B - PART 2: DYNAMIC STORAGE IMAGE LINKING ENGINE & RETRY PIPELINE
                        # =============================================================================
                        ans = ""
                        for attempt in range(5):
                            try:
                                response = client.models.generate_content(model='gemini-2.5-flash', contents=contents_payload)
                                ans = response.text
                                break
                            except Exception as e:
                                if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e) or "EXHAUSTED" in str(e):
                                    if attempt < 4:
                                        import time
                                        time.sleep(3 * (attempt + 1))
                                        continue
                                raise e
                                
                        st.write(ans)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": ans})
                        
                        # ✨ ĐỘT PHÁ TỰ ĐỘNG GỌI KHO ẢNH CHUYÊN NGHIỆP:
                        # Nếu database thong_so_techpack không trả về URL, hệ thống sẽ tự động lấy từ khóa sạch 'dynamic_keyword' (ví dụ: R09-490416)
                        # Để tự cấu trúc chính xác đường link public dẫn thẳng đến file ảnh .jpg trong bucket kho_anh của bạn!
                        final_render_url = ""
                        final_caption_title = ""
                        
                        if detected_image_url_to_render:
                            final_render_url = detected_image_url_to_render
                            final_caption_title = detected_style_title_to_render
                        elif dynamic_keyword and str(dynamic_keyword).strip() != "":
                            clean_style_id = str(dynamic_keyword).strip()
                            # Tự động ghép nối đường dẫn URL công khai dẫn thẳng tới file ảnh lưu trữ thực tế trong kho của bạn
                            final_render_url = f"{SB_URL.rstrip('/')}/storage/v1/object/public/kho_anh/{clean_style_id}.jpg"
                            final_caption_title = clean_style_id

                        # Kích hoạt hiển thị trực quan sơ đồ phác thảo phẳng (Garment Flat Sketch) lên khung chat
                        if final_render_url:
                            st.markdown("<br>", unsafe_allow_html=True)
                            # Hiển thị ảnh dạng Card thu nhỏ chuyên nghiệp, tránh tràn khung hình
                            st.image(final_render_url, caption=f"📐 Bản vẽ Sketch thiết kế đối chiếu của Mã hàng: {final_caption_title}", width=240)
                            
                            # Lưu hình ảnh này vào lịch sử trò chuyện để không bị biến mất khi trang web làm mới (Rerun)
                            st.session_state["chat_history"].append({
                                "role": "assistant", 
                                "type": "visual", 
                                "content": f"[Hệ thống đã xuất hình ảnh tham chiếu công khai của mã {final_caption_title} từ kho lưu trữ lên màn hình]",
                                "image_url": final_render_url,
                                "style_title": final_caption_title
                            })
                            
                    except Exception as e: 
                        ans = f"⚠️ Máy chủ AI đang xử lý tác vụ tra cứu kho lớn. Vui lòng thử lại sau vài giây! Chi tiết: {str(e)}"
                        st.write(ans)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": ans})
