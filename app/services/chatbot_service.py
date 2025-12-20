from typing import Optional, List, Dict
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from flask import current_app
import os
import re


def _get_sql_database():
    try:
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        
        db = SQLDatabase.from_uri(
            db_uri,
            include_tables=None,
            sample_rows_in_table_info=3,
            view_support=True,
        )
        
        return db
        
    except Exception as e:
        current_app.logger.error(f"Error connecting to database: {e}")
        raise


def _get_sql_agent():
    try:
        db = _get_sql_database()
        
        api_key = current_app.config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY chưa được cấu hình. "
                "Hãy thêm vào file .env, ví dụ: OPENAI_API_KEY=sk-..."
            )
        
        model_name = current_app.config.get('OPENAI_MODEL', 'gpt-4o-mini')
        
        llm = ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=api_key,
            request_timeout=30
        )
        
        agent = create_sql_agent(
            llm=llm,
            db=db,
            agent_type='openai-functions',
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=7,
            max_execution_time=45,
        )
        
        return agent, db
        
    except Exception as e:
        current_app.logger.error(f"Error creating SQL agent: {e}")
        raise


def _build_enhanced_prompt(message: str, db_info: str) -> str:
    prompt = f"""
Bạn là SQL Expert của hệ thống đặt phòng khách sạn HotelBooking.

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
   
   📌 Tìm phòng theo giá + số người:
   SELECT 
       r.room_id,
       r.room_name,
       r.base_price,
       r.max_guests,
       r.area,
       h.hotel_name,
       h.city,
       h.address
   FROM rooms r
   INNER JOIN hotels h ON r.hotel_id = h.hotel_id
   WHERE h.status = 'active'
   AND r.base_price BETWEEN [min_price] AND [max_price]
   AND r.max_guests >= [num_people]
   ORDER BY r.base_price ASC
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


def get_chatbot_answer(
    message: str,
    history: Optional[List[Dict[str, str]]] = None
) -> str:
    try:
        agent, db = _get_sql_agent()
        
        db_info = db.get_table_info()
        
        current_app.logger.info(f"=== AUTO-DETECTED SCHEMA ===\n{db_info}")
        
        enhanced_message = _build_enhanced_prompt(message, db_info)
        
        if history:
            context = "\n\n📝 LỊCH SỬ HỘI THOẠI GẦN ĐÂY:\n"
            for item in history[-3:]:
                role = "User" if item['role'] == 'user' else "Bot"
                context += f"{role}: {item['content']}\n"
            enhanced_message = context + "\n" + enhanced_message
        
        current_app.logger.info(f"User query: {message}")
        response = agent.invoke({"input": enhanced_message})
        
        answer = response.get("output", "")
        
        answer = _post_process_answer(answer, message)
        
        current_app.logger.info(f"Agent response: {answer}")
        
        return answer
        
    except TimeoutError:
        current_app.logger.warning("SQL Agent timeout, using fallback")
        return _fallback_simple_query(message)
        
    except Exception as e:
        error_msg = str(e)
        current_app.logger.error(f"SQL Agent error: {error_msg}", exc_info=True)
        
        if "iteration limit" in error_msg.lower() or "time limit" in error_msg.lower() or "max_iterations" in error_msg.lower():
            current_app.logger.info("Agent hit limit, using fallback")
            return _fallback_simple_query(message)
        
        return (
            "Xin lỗi, mình gặp lỗi khi xử lý yêu cầu. "
            "Bạn có thể thử hỏi lại với cách khác được không? "
            "Ví dụ: 'Tìm phòng ở Đà Lạt giá dưới 2 triệu'"
        )


def _post_process_answer(answer: str, original_message: str) -> str:
    answer = re.sub(r'```sql.*?```', '', answer, flags=re.DOTALL)
    answer = re.sub(r'SELECT.*?;', '', answer, flags=re.IGNORECASE)
    
    if any(keyword in answer.lower() for keyword in ['tìm được', 'có', 'phòng', 'khách sạn']):
        if 'bạn muốn' not in answer.lower():
            answer += "\n\nBạn muốn biết thêm chi tiết phòng nào không?"
    
    elif any(keyword in answer.lower() for keyword in ['không tìm thấy', 'không có', 'chưa có']):
        if 'bạn có thể' not in answer.lower():
            answer += "\n\nBạn có thể thử tìm ở địa điểm khác hoặc điều chỉnh khoảng giá?"
    
    return answer.strip()


def _fallback_simple_query(message: str) -> str:
    from app.models.hotel import Hotel
    from app.models.room import Room
    
    message_lower = message.lower()
    
    try:
        if any(city in message_lower for city in ['đà lạt', 'đà nẵng', 'nha trang', 'hà nội', 'hồ chí minh', 'vũng tàu']):
            cities = Hotel.query.filter(
                Hotel.status == 'active'
            ).with_entities(Hotel.city).distinct().all()
            
            cities_list = [c[0] for c in cities if c[0]]
            if cities_list:
                return f"Mình có khách sạn ở: {', '.join(cities_list)}. Bạn muốn xem chi tiết địa điểm nào?"
            else:
                return "Hiện tại mình chưa có khách sạn ở địa điểm bạn hỏi. Bạn có muốn xem các địa điểm khác không?"
        
        elif any(kw in message_lower for kw in ['giá', 'bao nhiêu', 'triệu', 'tr', 'k']):
            rooms = Room.query.join(Hotel).filter(
                Hotel.status == 'active'
            ).order_by(Room.base_price).limit(5).all()
            
            if rooms:
                result = "Một số phòng phù hợp:\n"
                for r in rooms:
                    result += f"- {r.room_name} tại {r.hotel.hotel_name}: {int(r.base_price):,}đ/đêm\n"
                return result
            else:
                return "Hiện tại mình chưa có phòng nào. Bạn có thể thử lại sau nhé."
        
        else:
            hotel_count = Hotel.query.filter(Hotel.status == 'active').count()
            room_count = Room.query.join(Hotel).filter(Hotel.status == 'active').count()
            
            return (
                f"Mình hiện có {hotel_count} khách sạn với {room_count} phòng. "
                f"Bạn muốn tìm theo địa điểm, giá cả, hay số người ở?"
            )
            
    except Exception as e:
        current_app.logger.error(f"Fallback query failed: {e}", exc_info=True)
        return "Xin lỗi, có lỗi xảy ra. Bạn thử lại sau nhé."
