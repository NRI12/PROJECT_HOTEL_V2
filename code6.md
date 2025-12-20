GIẢI PHÁP: 3 CÁCH FIX
CÁCH 1: TĂNG GIỚI HẠN (Quick fix) ⚡
pythondef _get_sql_agent():
    agent = create_sql_agent(
        llm=llm,
        db=db,
        agent_type=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10,      # ✅ Tăng lên 10
        max_execution_time=60,  # ✅ Tăng lên 60s
    )
    return agent, db
Nhược điểm: Chỉ giải quyết tạm thời, vẫn có thể lỗi với query phức tạp.

CÁCH 2: HƯỚNG DẪN AGENT RÕ RÀNG HƠN ⭐ (Khuyên dùng)
Sửa lại prompt để Agent viết SQL ĐÚNG NGAY LẦN ĐẦU:
pythondef _build_enhanced_prompt(message: str, db_info: str) -> str:
    prompt = f"""
Bạn là SQL Expert của hệ thống đặt phòng khách sạn.

🗄️ DATABASE SCHEMA:
{db_info}

🎯 CÂU HỎI: "{message}"

⚡ QUY TẮC QUAN TRỌNG - ĐỌC KỸ:

1. CHỈ ĐƯỢC VIẾT 1 QUERY DUY NHẤT
   - Không thử nhiều query
   - Phải chắc chắn query đúng 100% mới chạy

2. LUÔN BAO GỒM:
   ✅ WHERE h.status = 'active' (nếu có bảng hotels với alias h)
   ✅ LIMIT 5 (nếu user không yêu cầu số lượng cụ thể)
   ✅ JOIN đúng foreign keys

3. XỬ LÝ GIÁ TIỀN:
   - "1tr" = 1000000
   - "2 triệu" = 2000000  
   - "500k" = 500000
   - Dùng: price_per_night BETWEEN min AND max

4. XỬ LÝ ĐỊA ĐIỂM:
   - Dùng: city = 'tên_chính_xác'
   - Hoặc: city LIKE '%keyword%' (nếu không chắc)

5. XỬ LÝ SỐ NGƯỜI:
   - "4 người" = max_occupancy >= 4

6. TEMPLATE CỐ ĐỊNH - SỬ DỤNG THEO MẪU:

   📌 Tìm phòng theo giá + số người:
   SELECT 
       r.room_id,
       r.room_name,
       r.price_per_night,
       r.max_occupancy,
       r.room_size,
       h.hotel_name,
       h.city,
       h.address
   FROM rooms r
   INNER JOIN hotels h ON r.hotel_id = h.hotel_id
   WHERE h.status = 'active'
   AND r.price_per_night BETWEEN [min_price] AND [max_price]
   AND r.max_occupancy >= [num_people]
   ORDER BY r.price_per_night ASC
   LIMIT 5;

   📌 Tìm khách sạn theo địa điểm:
   SELECT 
       h.hotel_id,
       h.hotel_name,
       h.city,
       h.star_rating,
       h.address,
       COUNT(r.room_id) as room_count
   FROM hotels h
   LEFT JOIN rooms r ON h.hotel_id = r.hotel_id
   WHERE h.status = 'active'
   AND h.city = '[city_name]'
   GROUP BY h.hotel_id
   LIMIT 5;

   📌 Top khách sạn theo đánh giá:
   SELECT 
       h.hotel_id,
       h.hotel_name,
       h.city,
       AVG(rv.rating) as avg_rating,
       COUNT(rv.review_id) as review_count
   FROM hotels h
   INNER JOIN reviews rv ON h.hotel_id = rv.hotel_id
   WHERE h.status = 'active'
   GROUP BY h.hotel_id
   HAVING review_count >= 3
   ORDER BY avg_rating DESC
   LIMIT 5;

🚨 NẾU KHÔNG CHẮC CHẮN:
- Query đơn giản nhất có thể
- Ví dụ: chỉ SELECT * FROM hotels WHERE status='active' LIMIT 5

📤 SAU KHI CÓ KẾT QUẢ:
- Format bằng tiếng Việt
- Hiển thị tối đa 5 kết quả
- Không show SQL query cho user

BẮT ĐẦU!
"""
    return prompt

CÁCH 3: SỬ DỤNG ZERO-SHOT AGENT 🎯 (Production-ready)
Thay vì để Agent tự do, cung cấp sẵn SQL templates:
pythonfrom langchain.agents import create_sql_agent, AgentExecutor
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.prompts import PromptTemplate

def _get_optimized_sql_agent():
    """SQL Agent tối ưu với pre-defined patterns"""
    
    db = _get_sql_database()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=current_app.config['OPENAI_API_KEY']
    )
    
    # ✅ TẠO TOOLKIT
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    # ✅ CUSTOM PROMPT CHO AGENT
    prefix = """
Bạn là SQL expert. Nhiệm vụ: viết 1 query SQL duy nhất để trả lời câu hỏi.

Database schema:
{input}

QUAN TRỌNG:
- Chỉ viết 1 query, không retry
- Luôn thêm WHERE status='active' nếu có cột status
- Luôn thêm LIMIT 5
- Format kết quả bằng tiếng Việt

Nếu không chắc chắn, hãy viết query đơn giản nhất.
"""
    
    # ✅ TẠO AGENT VỚI CUSTOM SETTINGS
    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        prefix=prefix,
        verbose=True,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # ✅ Thay đổi agent type
        max_iterations=3,  # ✅ Giảm xuống 3 để fail-fast
        max_execution_time=20,  # ✅ Giảm xuống 20s
        early_stopping_method="generate",  # ✅ Dừng sớm nếu có lỗi
        handle_parsing_errors=True,
    )
    
    return agent, db

CÁCH 4: FALLBACK MECHANISM 🛡️ (Best practice)
Khi Agent fail, tự động fallback sang query đơn giản:
pythondef get_chatbot_answer(message: str, history=None) -> str:
    try:
        agent, db = _get_sql_agent()
        db_info = db.get_table_info()
        enhanced_message = _build_enhanced_prompt(message, db_info)
        
        # ✅ TRY AGENT FIRST
        response = agent.invoke({"input": enhanced_message})
        answer = response.get("output", "")
        
        return _post_process_answer(answer, message)
        
    except Exception as e:
        error_msg = str(e)
        current_app.logger.error(f"SQL Agent failed: {error_msg}")
        
        # ✅ FALLBACK: QUERY ĐỐN GIẢN TRỰC TIẾP
        if "iteration limit" in error_msg or "time limit" in error_msg:
            return _fallback_simple_query(message)
        
        return "Xin lỗi, mình gặp lỗi. Bạn thử hỏi đơn giản hơn nhé?"


def _fallback_simple_query(message: str) -> str:
    """
    Khi Agent fail, query trực tiếp bằng SQLAlchemy
    """
    from app.models import Hotel, Room
    from sqlalchemy import and_, or_
    
    message_lower = message.lower()
    
    try:
        # ✅ CASE 1: Hỏi về địa điểm
        if any(city in message_lower for city in ['đà lạt', 'đà nẵng', 'nha trang', 'hà nội']):
            cities = Hotel.query.filter(
                Hotel.status == 'active'
            ).with_entities(Hotel.city).distinct().all()
            
            cities_list = [c[0] for c in cities if c[0]]
            return f"Mình có khách sạn ở: {', '.join(cities_list)}. Bạn muốn xem chi tiết địa điểm nào?"
        
        # ✅ CASE 2: Hỏi về giá
        elif any(kw in message_lower for kw in ['giá', 'bao nhiêu', 'triệu', 'tr']):
            rooms = Room.query.join(Hotel).filter(
                Hotel.status == 'active'
            ).order_by(Room.price_per_night).limit(5).all()
            
            if rooms:
                result = "Một số phòng phù hợp:\n"
                for r in rooms:
                    result += f"- {r.room_name} tại {r.hotel.hotel_name}: {r.price_per_night:,}đ/đêm\n"
                return result
        
        # ✅ CASE 3: Hỏi chung chung
        else:
            hotel_count = Hotel.query.filter(Hotel.status == 'active').count()
            room_count = Room.query.count()
            
            return (
                f"Mình hiện có {hotel_count} khách sạn với {room_count} phòng. "
                f"Bạn muốn tìm theo địa điểm, giá cả, hay số người ở?"
            )
            
    except Exception as e:
        current_app.logger.error(f"Fallback query failed: {e}")
        return "Xin lỗi, có lỗi xảy ra. Bạn thử lại sau nhé."