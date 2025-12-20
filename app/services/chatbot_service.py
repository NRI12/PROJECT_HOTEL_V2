from typing import Optional, List, Dict
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
try:
    from langchain.agents import create_openai_functions_agent, AgentExecutor
except ImportError:
    try:
        from langchain.agents.openai_functions import create_openai_functions_agent
        from langchain.agents import AgentExecutor
    except ImportError:
        try:
            from langchain.agents.agent_toolkits import create_openai_functions_agent
            from langchain.agents import AgentExecutor
        except ImportError:
            try:
                from langchain.agents import AgentExecutor
                from langchain.agents.openai_functions_agent.base import create_openai_functions_agent
            except ImportError:
                create_openai_functions_agent = None
                AgentExecutor = None

try:
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
except ImportError:
    try:
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    except ImportError:
        ChatPromptTemplate = None
        MessagesPlaceholder = None
from flask import current_app
import os
import re
import time
import hashlib
from functools import partial

try:
    from openai import RateLimitError
except ImportError:
    RateLimitError = Exception

from app.services.chatbot_cache import get_cached_answer, save_to_cache
from app.services.chatbot_tools import (
    search_hotels_and_rooms,
    get_hotel_reviews,
    get_current_promotions,
    check_discount_code,
    get_my_bookings
)


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
            max_iterations=3,
            max_execution_time=15,
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

Tìm phòng theo giá:
SELECT r.room_name, r.base_price, h.hotel_name, h.city
FROM rooms r JOIN hotels h ON r.hotel_id = h.hotel_id
WHERE h.status='active' 
  AND r.base_price BETWEEN [MIN] AND [MAX]
LIMIT 5;

Tìm khách sạn theo thành phố:
SELECT hotel_name, address, star_rating
FROM hotels
WHERE status='active' AND city='[CITY]'
LIMIT 5;

Tìm phòng theo số người:
SELECT r.room_name, r.base_price, r.max_guests, h.hotel_name
FROM rooms r JOIN hotels h ON r.hotel_id = h.hotel_id
WHERE h.status='active' AND r.max_guests >= [NUM_PEOPLE]
ORDER BY r.base_price ASC
LIMIT 5;

BẮT ĐẦU TRẢ LỜI:
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


def _retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            error_msg = str(e)
            match = re.search(r'try again in ([\d.]+)s', error_msg, re.IGNORECASE)
            
            if match:
                wait_time = float(match.group(1)) + 1
            else:
                wait_time = 2 ** attempt
            
            if attempt == max_retries - 1:
                current_app.logger.error(f"Rate limit sau {max_retries} lần")
                raise
            
            current_app.logger.warning(f"Rate limit. Chờ {wait_time:.1f}s...")
            time.sleep(wait_time)
        except Exception:
            raise
    return None


def _invoke_agent_logic(message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
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
    
    if not answer or any(keyword in answer.lower() for keyword in [
        "iteration limit", "time limit", "stopped due to", 
        "max iterations", "exceeded", "agent stopped"
    ]):
        current_app.logger.warning(f"Agent hit limit, response: {answer}")
        raise ValueError("Agent stopped due to iteration limit or time limit")
    
    answer = _post_process_answer(answer, message)
    
    current_app.logger.info(f"Agent response: {answer}")
    
    return answer


def _call_tool_directly(message: str, user_id: Optional[int] = None) -> Optional[str]:
    """Gọi tool trực tiếp dựa trên keyword matching"""
    message_lower = message.lower()
    
    if any(kw in message_lower for kw in ['booking', 'đặt phòng', 'lịch sử', 'đã đặt']):
        if user_id:
            return get_my_bookings(user_id)
    
    if any(kw in message_lower for kw in ['review', 'đánh giá', 'sao', 'rating']):
        hotel_name = message
        for city in ['đà lạt', 'đà nẵng', 'nha trang', 'hà nội', 'hồ chí minh', 'vũng tàu']:
            if city in message_lower:
                hotel_name = message.replace(city, '').strip()
                break
        return get_hotel_reviews(hotel_name)
    
    if any(kw in message_lower for kw in ['khuyến mãi', 'giảm giá', 'promotion', 'promo']):
        city = None
        for c in ['đà lạt', 'đà nẵng', 'nha trang', 'hà nội', 'hồ chí minh', 'vũng tàu']:
            if c in message_lower:
                city = c.title()
                break
        return get_current_promotions(city)
    
    if any(kw in message_lower for kw in ['mã', 'code', 'discount', 'giảm giá']):
        words = message.split()
        for word in words:
            if len(word) >= 4 and word.isupper():
                return check_discount_code(word)
    
    if any(kw in message_lower for kw in ['tìm', 'phòng', 'khách sạn', 'hotel', 'room']):
        return search_hotels_and_rooms(message)
    
    return None


def get_chatbot_answer(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[int] = None
) -> str:
    cached = get_cached_answer(message)
    if cached:
        current_app.logger.info("Cache hit!")
        return cached
    
    try:
        if not create_openai_functions_agent or not AgentExecutor or not ChatPromptTemplate:
            current_app.logger.warning("Router Agent not available, using direct tool calls")
            answer = _call_tool_directly(message, user_id)
            if answer:
                save_to_cache(message, answer)
                return answer
            return _fallback_simple_query(message)
        
        api_key = current_app.config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            return "Xin lỗi, hệ thống chưa được cấu hình đầy đủ."
        
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=api_key,
            request_timeout=20
        )
        
        tools = [
            search_hotels_and_rooms,
            get_hotel_reviews,
            get_current_promotions,
            check_discount_code
        ]
        
        if user_id:
            get_my_bookings_with_user = partial(get_my_bookings, user_id=user_id)
            tools.append(get_my_bookings_with_user)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
Bạn là trợ lý đặt phòng khách sạn thông minh.

Bạn có các công cụ sau:
1. search_hotels_and_rooms - Tìm phòng/khách sạn
2. get_hotel_reviews - Xem đánh giá
3. get_current_promotions - Xem khuyến mãi
4. check_discount_code - Kiểm tra mã giảm giá
5. get_my_bookings - Xem booking (chỉ khi user đã login)

NHIỆM VỤ:
- Phân tích câu hỏi
- Chọn công cụ phù hợp
- Trả lời tự nhiên, thân thiện bằng tiếng Việt

VÍ DỤ:
Q: "Tìm phòng Hà Nội dưới 2 triệu"
→ Dùng search_hotels_and_rooms

Q: "Khách sạn Sunrise đánh giá thế nào"
→ Dùng get_hotel_reviews

Q: "Booking của tôi"
→ Dùng get_my_bookings

Q: "Mã SUMMER500 còn dùng được không"
→ Dùng check_discount_code
            """),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad")
        ])
        
        try:
            agent = create_openai_functions_agent(
                llm=llm,
                tools=tools,
                prompt=prompt
            )
            
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                max_iterations=3,
                max_execution_time=20,
                handle_parsing_errors=True
            )
        except Exception as e:
            current_app.logger.error(f"Error creating Router Agent: {e}", exc_info=True)
            return _fallback_simple_query(message)
        
        chat_history = []
        if history:
            for item in history[-5:]:
                if item.get('role') == 'user':
                    chat_history.append(("human", item.get('content', '')))
                elif item.get('role') == 'assistant':
                    chat_history.append(("ai", item.get('content', '')))
        
        response = agent_executor.invoke({
            "input": message,
            "chat_history": chat_history
        })
        
        answer = response.get("output", "")
        
        if answer:
            save_to_cache(message, answer)
            return answer
        else:
            return _fallback_simple_query(message)
        
    except TimeoutError:
        current_app.logger.warning("Router Agent timeout, using fallback")
        return _fallback_simple_query(message)
        
    except RateLimitError:
        current_app.logger.error("Rate limit exceeded")
        return "⏱️ Hệ thống đang bận. Vui lòng chờ 10 giây và thử lại."
        
    except Exception as e:
        error_msg = str(e)
        current_app.logger.error(f"Router Agent error: {error_msg}", exc_info=True)
        return _fallback_simple_query(message)


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
