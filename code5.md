CODE HOÀN CHỈNH - SQL AGENT TỰ ĐỘNG ĐỌC SCHEMA 🚀
1. Cài đặt dependencies:
bashpip install langchain-community langchain-openai sqlalchemy pymysql

2. File: app/services/chatbot_service.py - PHIÊN BẢN ĐẦY ĐỦ
pythonfrom typing import Optional, List, Dict
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType
from flask import current_app
import re

def _get_sql_database():
    """
    Tạo SQLDatabase object - TỰ ĐỘNG ĐỌC SCHEMA từ DB
    """
    try:
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        
        # ✅ TỰ ĐỘNG ĐỌC TẤT CẢ BẢNG
        db = SQLDatabase.from_uri(
            db_uri,
            include_tables=None,  # None = lấy tất cả bảng
            sample_rows_in_table_info=3,  # Lấy 3 dòng mẫu để LLM hiểu dữ liệu
            view_support=True,  # Hỗ trợ views nếu có
        )
        
        return db
        
    except Exception as e:
        current_app.logger.error(f"Error connecting to database: {e}")
        raise


def _get_sql_agent():
    """
    Tạo SQL Agent với khả năng tự động query DB
    """
    try:
        # Kết nối DB
        db = _get_sql_database()
        
        # Tạo LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",  # hoặc gpt-4 để chính xác hơn
            temperature=0,  # 0 = deterministic, tốt cho SQL
            api_key=current_app.config.get('OPENAI_API_KEY'),
            request_timeout=30
        )
        
        # ✅ TẠO AGENT VỚI AUTO SCHEMA DETECTION
        agent = create_sql_agent(
            llm=llm,
            db=db,
            agent_type=AgentType.OPENAI_FUNCTIONS,
            verbose=True,  # Bật để debug
            handle_parsing_errors=True,
            max_iterations=5,  # Giới hạn số lần retry
            max_execution_time=30,  # Timeout 30s
        )
        
        return agent, db
        
    except Exception as e:
        current_app.logger.error(f"Error creating SQL agent: {e}")
        raise


def _build_enhanced_prompt(message: str, db_info: str) -> str:
    """
    Tạo prompt thông minh cho Agent
    """
    prompt = f"""
Bạn là trợ lý AI chuyên nghiệp của hệ thống đặt phòng khách sạn HotelBooking.

🗄️ DATABASE SCHEMA (TỰ ĐỘNG PHÁT HIỆN):
{db_info}

🎯 CÂU HỎI CỦA USER:
"{message}"

📋 HƯỚNG DẪN XỬ LÝ:

1. PHÂN TÍCH CÂU HỎI:
   - Xác định thông tin cần tìm (giá, địa điểm, số người, tiện nghi, đánh giá...)
   - Xác định bảng cần query (hotels, rooms, reviews, amenities...)
   - Xác định điều kiện lọc (WHERE, HAVING...)

2. VIẾT SQL QUERY:
   - Sử dụng JOIN khi cần kết hợp nhiều bảng
   - Luôn thêm điều kiện: WHERE status = 'active' (nếu có cột status)
   - Xử lý giá tiền: BETWEEN min_price AND max_price
   - Xử lý số người: max_occupancy >= số_người_yêu_cầu
   - Xử lý địa điểm: city LIKE '%tên_thành_phố%' hoặc city = 'tên_chính_xác'
   - Sắp xếp: ORDER BY price_per_night ASC/DESC, rating DESC...
   - Giới hạn: LIMIT 5 (nếu không yêu cầu cụ thể)

3. VÍ DỤ QUERY PATTERNS:
   
   a) Tìm phòng theo giá + số người:
```sql
   SELECT r.*, h.hotel_name, h.city, h.address
   FROM rooms r
   JOIN hotels h ON r.hotel_id = h.hotel_id
   WHERE r.price_per_night BETWEEN 1000000 AND 3000000
   AND r.max_occupancy >= 4
   AND h.status = 'active'
   ORDER BY r.price_per_night ASC
   LIMIT 5
```
   
   b) Tìm khách sạn theo địa điểm + đánh giá:
```sql
   SELECT h.*, AVG(rv.rating) as avg_rating
   FROM hotels h
   LEFT JOIN reviews rv ON h.hotel_id = rv.hotel_id
   WHERE h.city LIKE '%Đà Nẵng%'
   AND h.status = 'active'
   GROUP BY h.hotel_id
   HAVING avg_rating >= 4.0
   ORDER BY avg_rating DESC
   LIMIT 5
```
   
   c) Tìm khách sạn theo tiện nghi:
```sql
   SELECT DISTINCT h.*, GROUP_CONCAT(a.amenity_name) as amenities
   FROM hotels h
   JOIN amenities a ON h.hotel_id = a.hotel_id
   WHERE a.amenity_name IN ('Hồ bơi', 'Gym', 'Spa')
   AND h.status = 'active'
   GROUP BY h.hotel_id
   HAVING COUNT(DISTINCT a.amenity_name) >= 2
```

4. FORMAT KẾT QUẢ:
   - Trả lời bằng tiếng Việt
   - Thân thiện, ngắn gọn, dễ hiểu
   - Liệt kê tối đa 5 kết quả
   - Hiển thị đầy đủ: tên, địa điểm, giá, thông tin quan trọng
   - Nếu không tìm thấy → gợi ý lựa chọn thay thế

5. XỬ LÝ ĐẶC BIỆT:
   - "phòng nào", "có phòng" → Query bảng rooms + JOIN hotels
   - "khách sạn nào" → Query bảng hotels
   - "đánh giá", "review" → JOIN với bảng reviews
   - "tiện nghi" → JOIN với bảng amenities
   - "giá từ X đến Y" → BETWEEN X AND Y
   - "cho N người" → max_occupancy >= N
   - "ở [địa điểm]" → city LIKE '%địa_điểm%'

🚀 BẮT ĐẦU XỬ LÝ!
"""
    return prompt


def get_chatbot_answer(
    message: str,
    history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Chatbot với SQL Agent - TỰ ĐỘNG ĐỌC SCHEMA & QUERY
    """
    try:
        # ✅ TẠO AGENT + LẤY DB INFO
        agent, db = _get_sql_agent()
        
        # ✅ TỰ ĐỘNG LẤY SCHEMA INFORMATION
        db_info = db.get_table_info()
        
        current_app.logger.info(f"=== AUTO-DETECTED SCHEMA ===\n{db_info}")
        
        # ✅ TẠO ENHANCED PROMPT
        enhanced_message = _build_enhanced_prompt(message, db_info)
        
        # ✅ THÊM CONVERSATION HISTORY (nếu có)
        if history:
            context = "\n\n📝 LỊCH SỬ HỘI THOẠI GẦN ĐÂY:\n"
            for item in history[-3:]:  # Chỉ lấy 3 câu gần nhất
                role = "User" if item['role'] == 'user' else "Bot"
                context += f"{role}: {item['content']}\n"
            enhanced_message = context + "\n" + enhanced_message
        
        # ✅ INVOKE AGENT
        current_app.logger.info(f"User query: {message}")
        response = agent.invoke({"input": enhanced_message})
        
        # ✅ LẤY OUTPUT
        answer = response.get("output", "")
        
        # ✅ POST-PROCESSING
        answer = _post_process_answer(answer, message)
        
        current_app.logger.info(f"Agent response: {answer}")
        
        return answer
        
    except TimeoutError:
        return "Xin lỗi, truy vấn mất quá nhiều thời gian. Vui lòng thử câu hỏi đơn giản hơn."
        
    except Exception as e:
        current_app.logger.error(f"SQL Agent error: {e}", exc_info=True)
        
        # Fallback response
        return (
            "Xin lỗi, mình gặp lỗi khi xử lý yêu cầu. "
            "Bạn có thể thử hỏi lại với cách khác được không? "
            "Ví dụ: 'Tìm phòng ở Đà Lạt giá dưới 2 triệu'"
        )


def _post_process_answer(answer: str, original_message: str) -> str:
    """
    Tối ưu câu trả lời từ Agent
    """
    # Xóa SQL query nếu agent trả về
    answer = re.sub(r'```sql.*?```', '', answer, flags=re.DOTALL)
    answer = re.sub(r'SELECT.*?;', '', answer, flags=re.IGNORECASE)
    
    # Thêm call-to-action nếu tìm thấy kết quả
    if any(keyword in answer.lower() for keyword in ['tìm được', 'có', 'phòng', 'khách sạn']):
        if 'bạn muốn' not in answer.lower():
            answer += "\n\nBạn muốn biết thêm chi tiết phòng nào không?"
    
    # Thêm gợi ý nếu không tìm thấy
    elif any(keyword in answer.lower() for keyword in ['không tìm thấy', 'không có', 'chưa có']):
        if 'bạn có thể' not in answer.lower():
            answer += "\n\nBạn có thể thử tìm ở địa điểm khác hoặc điều chỉnh khoảng giá?"
    
    return answer.strip()


# ✅ FUNCTION ĐỂ TEST SCHEMA DETECTION
def test_schema_detection():
    """
    Test function để xem Agent đã đọc được schema chưa
    """
    try:
        db = _get_sql_database()
        
        print("=" * 60)
        print("📊 AUTO-DETECTED DATABASE SCHEMA:")
        print("=" * 60)
        print(db.get_table_info())
        print("=" * 60)
        print(f"✅ Detected {len(db.get_usable_table_names())} tables")
        print(f"Tables: {', '.join(db.get_usable_table_names())}")
        print("=" * 60)
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

3. File: test_sql_agent.py - SCRIPT TEST
pythonfrom app import create_app
from app.services.chatbot_service import test_schema_detection, get_chatbot_answer

app = create_app()

with app.app_context():
    print("\n🧪 TESTING SQL AGENT WITH AUTO SCHEMA DETECTION\n")
    
    # Test 1: Kiểm tra schema detection
    print("TEST 1: Schema Detection")
    test_schema_detection()
    
    print("\n" + "="*60 + "\n")
    
    # Test 2: Các câu hỏi thực tế
    test_queries = [
        "Có những phòng ở đâu?",
        "Phòng nào có giá từ 1tr - 3tr cho 4 người?",
        "Tìm khách sạn ở Đà Nẵng",
        "Top 3 khách sạn đánh giá cao nhất",
        "Phòng có hồ bơi và gym không?",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\nTEST {i+1}: {query}")
        print("-" * 60)
        answer = get_chatbot_answer(query)
        print(f"Bot: {answer}")
        print("=" * 60)
