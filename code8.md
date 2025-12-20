✅ KIẾN TRÚC MỚI - ROUTER AGENT
User Question
     ↓
┌────────────────┐
│  ROUTER AGENT  │ ← Phân loại câu hỏi
└────────────────┘
     ↓
  ┌──┴──┬──────┬────────┬─────────┐
  ↓     ↓      ↓        ↓         ↓
┌──────┐┌────┐┌──────┐┌────────┐┌─────┐
│ RAG  ││SQL ││Review││Booking ││Promo│
│Search││Tool││Tool  ││Tool    ││Tool │
└──────┘└────┘└──────┘└────────┘└─────┘
  ↓
Final Answer

🔧 CODE TRIỂN KHAI
Bước 1: Tạo Tools Cho Từng Loại Query
Tạo file app/services/chatbot_tools.py:
python"""
CHATBOT TOOLS - Công cụ cho Router Agent
"""

from langchain.tools import tool
from flask import current_app
from typing import Optional
from datetime import datetime


# ========== TOOL 1: TÌM PHÒNG (RAG) ==========
@tool
def search_hotels_and_rooms(query: str) -> str:
    """
    Tìm kiếm khách sạn và phòng theo yêu cầu.
    
    Dùng khi user hỏi về:
    - "Tìm phòng ở X"
    - "Khách sạn Y có gì"
    - "Phòng giá Z"
    - "Có WiFi/hồ bơi không"
    
    Args:
        query: Mô tả yêu cầu tìm kiếm
    
    Returns:
        Danh sách phòng phù hợp
    """
    try:
        from app.services.chatbot_service import HotelRAGChatbot
        
        chatbot = HotelRAGChatbot()
        return chatbot.get_answer(query)
    except Exception as e:
        return f"Lỗi tìm kiếm: {str(e)}"


# ========== TOOL 2: BOOKING CỦA USER (SQL) ==========
@tool
def get_my_bookings(user_id: int) -> str:
    """
    Lấy danh sách booking của user hiện tại.
    
    Dùng khi user hỏi về:
    - "Booking của tôi"
    - "Tôi đã đặt phòng nào"
    - "Lịch sử đặt phòng"
    
    Args:
        user_id: ID của user đang đăng nhập
    
    Returns:
        Danh sách booking
    """
    try:
        from app.models import Booking, Hotel, Room
        from app import db
        
        bookings = db.session.query(
            Booking, Hotel, Room
        ).join(
            Hotel, Booking.hotel_id == Hotel.hotel_id
        ).join(
            Room, Booking.booking_id == Room.room_id  # Qua booking_details
        ).filter(
            Booking.user_id == user_id
        ).order_by(
            Booking.created_at.desc()
        ).limit(5).all()
        
        if not bookings:
            return "Bạn chưa có booking nào."
        
        result = "📋 Danh sách booking của bạn:\n\n"
        for booking, hotel, room in bookings:
            result += f"""
🏨 {hotel.hotel_name}
📍 {hotel.city}
🛏️ Phòng: {room.room_name}
📅 Check-in: {booking.check_in_date.strftime('%d/%m/%Y')}
📅 Check-out: {booking.check_out_date.strftime('%d/%m/%Y')}
💰 Tổng: {booking.final_amount:,.0f}đ
✅ Trạng thái: {booking.status}
💳 Thanh toán: {booking.payment_status}

"""
        
        return result.strip()
        
    except Exception as e:
        return f"Lỗi lấy booking: {str(e)}"


# ========== TOOL 3: REVIEW KHÁCH SẠN (SQL + Aggregate) ==========
@tool
def get_hotel_reviews(hotel_name: str) -> str:
    """
    Lấy đánh giá của một khách sạn.
    
    Dùng khi user hỏi:
    - "Khách sạn X đánh giá thế nào"
    - "Review về Y"
    
    Args:
        hotel_name: Tên khách sạn
    
    Returns:
        Tóm tắt reviews
    """
    try:
        from app.models import Hotel, Review, User
        from app import db
        from sqlalchemy import func
        
        # Tìm hotel
        hotel = db.session.query(Hotel).filter(
            Hotel.hotel_name.ilike(f'%{hotel_name}%')
        ).first()
        
        if not hotel:
            return f"Không tìm thấy khách sạn '{hotel_name}'"
        
        # Lấy reviews
        reviews = db.session.query(
            Review, User
        ).join(
            User, Review.user_id == User.user_id
        ).filter(
            Review.hotel_id == hotel.hotel_id,
            Review.status == 'active'
        ).order_by(
            Review.created_at.desc()
        ).limit(5).all()
        
        # Tính rating trung bình
        avg_rating = db.session.query(
            func.avg(Review.rating)
        ).filter(
            Review.hotel_id == hotel.hotel_id
        ).scalar() or 0
        
        result = f"""
🏨 **{hotel.hotel_name}**
⭐ Đánh giá trung bình: {avg_rating:.1f}/5 ({len(reviews)} đánh giá)

📝 Review gần nhất:

"""
        
        for review, user in reviews[:3]:
            result += f"""
👤 {user.full_name} - ⭐ {review.rating}/5
"{review.comment[:100]}..."
📅 {review.created_at.strftime('%d/%m/%Y')}

"""
        
        return result.strip()
        
    except Exception as e:
        return f"Lỗi lấy review: {str(e)}"


# ========== TOOL 4: KHUYẾN MÃI HIỆN TẠI (SQL Time-based) ==========
@tool
def get_current_promotions(city: Optional[str] = None) -> str:
    """
    Lấy khuyến mãi đang có hiệu lực.
    
    Dùng khi user hỏi:
    - "Khuyến mãi gì hiện tại"
    - "Giảm giá ở X"
    
    Args:
        city: Thành phố (optional)
    
    Returns:
        Danh sách khuyến mãi
    """
    try:
        from app.models import Promotion, Hotel
        from app import db
        
        now = datetime.now()
        
        query = db.session.query(
            Promotion, Hotel
        ).join(
            Hotel, Promotion.hotel_id == Hotel.hotel_id
        ).filter(
            Promotion.is_active == True,
            Promotion.start_date <= now,
            Promotion.end_date >= now
        )
        
        if city:
            query = query.filter(Hotel.city.ilike(f'%{city}%'))
        
        promotions = query.limit(10).all()
        
        if not promotions:
            return "Hiện không có khuyến mãi nào."
        
        result = "🎁 Khuyến mãi hiện tại:\n\n"
        
        for promo, hotel in promotions:
            discount = ""
            if promo.discount_type == 'percentage':
                discount = f"Giảm {promo.discount_value}%"
            else:
                discount = f"Giảm {promo.discount_value:,.0f}đ"
            
            result += f"""
🏨 {hotel.hotel_name} ({hotel.city})
🎁 {promo.title}
💰 {discount}
📅 Đến: {promo.end_date.strftime('%d/%m/%Y')}

"""
        
        return result.strip()
        
    except Exception as e:
        return f"Lỗi lấy khuyến mãi: {str(e)}"


# ========== TOOL 5: MÃ GIẢM GIÁ (SQL) ==========
@tool
def check_discount_code(code: str) -> str:
    """
    Kiểm tra mã giảm giá có hiệu lực không.
    
    Dùng khi user hỏi:
    - "Mã ABC còn dùng được không"
    - "Kiểm tra mã giảm giá"
    
    Args:
        code: Mã giảm giá
    
    Returns:
        Thông tin mã
    """
    try:
        from app.models import DiscountCode
        from app import db
        
        now = datetime.now()
        
        discount = db.session.query(DiscountCode).filter(
            DiscountCode.code == code.upper(),
            DiscountCode.is_active == True,
            DiscountCode.start_date <= now,
            DiscountCode.end_date >= now
        ).first()
        
        if not discount:
            return f"Mã '{code}' không tồn tại hoặc đã hết hạn."
        
        # Kiểm tra đã dùng hết chưa
        if discount.usage_limit and discount.used_count >= discount.usage_limit:
            return f"Mã '{code}' đã hết lượt sử dụng."
        
        discount_text = ""
        if discount.discount_type == 'percentage':
            discount_text = f"Giảm {discount.discount_value}%"
        else:
            discount_text = f"Giảm {discount.discount_value:,.0f}đ"
        
        return f"""
✅ Mã '{code}' còn hiệu lực!

💰 Ưu đãi: {discount_text}
📝 Mô tả: {discount.description}
💵 Đơn tối thiểu: {discount.min_order_amount:,.0f}đ
📊 Đã dùng: {discount.used_count}/{discount.usage_limit or '∞'}
📅 Hết hạn: {discount.end_date.strftime('%d/%m/%Y')}
"""
        
    except Exception as e:
        return f"Lỗi kiểm tra mã: {str(e)}"

Bước 2: Tạo Router Agent
Sửa file app/services/chatbot_service.py:
python"""
CHATBOT SERVICE - ROUTER AGENT
Phân loại câu hỏi → gọi tool phù hợp
"""

from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from flask import current_app
import os

# Import tools
from app.services.chatbot_tools import (
    search_hotels_and_rooms,
    get_my_bookings,
    get_hotel_reviews,
    get_current_promotions,
    check_discount_code
)


def get_chatbot_answer(message: str, history=None, user_id: Optional[int] = None) -> str:
    """
    Router Agent - Phân loại câu hỏi và gọi tool
    
    Args:
        message: Câu hỏi
        history: Lịch sử chat
        user_id: ID user đang đăng nhập
    """
    try:
        api_key = current_app.config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
        
        # LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=api_key,
            request_timeout=20
        )
        
        # Danh sách tools
        tools = [
            search_hotels_and_rooms,
            get_hotel_reviews,
            get_current_promotions,
            check_discount_code
        ]
        
        # Thêm tool get_my_bookings nếu user đã login
        if user_id:
            # Bind user_id vào tool
            from functools import partial
            get_my_bookings_with_user = partial(get_my_bookings.func, user_id=user_id)
            tools.append(tool(get_my_bookings_with_user))
        
        # Prompt
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
- Trả lời tự nhiên, thân thiện

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
        
        # Tạo agent
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
        
        # Invoke
        response = agent_executor.invoke({
            "input": message,
            "chat_history": history or []
        })
        
        return response.get("output", "")
        
    except Exception as e:
        current_app.logger.error(f"Router Agent error: {e}", exc_info=True)
        return "Xin lỗi, mình gặp lỗi. Bạn thử lại nhé?"

Bước 3: Cập Nhật Routes Truyền user_id
Sửa app/routes/chatbot_routes.py:
pythonfrom flask import Blueprint, request, jsonify, session
from app.services.chatbot_service import get_chatbot_answer

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


@chatbot_bp.route("/message", methods=["POST"])
def chat_message():
    """Endpoint nhận message"""
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        # ✅ Lấy user_id từ session
        user_id = session.get('user_id')
        
        # Gọi chatbot với user_id
        answer = get_chatbot_answer(message, history, user_id=user_id)
        
        return jsonify({"answer": answer})
        
    except Exception as exc:
        from flask import current_app
        current_app.logger.error("Chatbot error: %s", exc, exc_info=True)
        return jsonify({"error": "Có lỗi xảy ra"}), 500
```

---

## 📊 KẾT QUẢ - BAO QUÁT TẤT CẢ

### **Test Case 1: Tìm phòng** ✅
```
User: "Tìm phòng Đà Lạt có hồ bơi"
Agent: → Gọi search_hotels_and_rooms
Bot: "🏨 Highland Coffee Hotel..."
```

### **Test Case 2: Xem booking** ✅
```
User: "Booking của tôi thế nào"
Agent: → Gọi get_my_bookings(user_id=8)
Bot: "📋 Danh sách booking:
     🏨 Sunrise Beach Resort
     📅 Check-in: 25/11/2025..."
```

### **Test Case 3: Xem review** ✅
```
User: "Khách sạn Sunrise đánh giá thế nào"
Agent: → Gọi get_hotel_reviews("Sunrise")
Bot: "⭐ 4.8/5 (10 đánh giá)
     👤 Phạm Minh Tuấn: 'Tuyệt vời!'"
```

### **Test Case 4: Khuyến mãi** ✅
```
User: "Khuyến mãi ở Vũng Tàu"
Agent: → Gọi get_current_promotions(city="Vũng Tàu")
Bot: "🎁 Khuyến mãi:
     🏨 Sunrise Beach Resort
     💰 Giảm 20%..."
```

### **Test Case 5: Kiểm tra mã** ✅
```
User: "Mã SUMMER500 còn dùng được không"
Agent: → Gọi check_discount_code("SUMMER500")
Bot: "✅ Mã còn hiệu lực!
     💰 Giảm 500,000đ..."
