## ❌ LỖI: THIẾU DOCSTRING

Lỗi này xảy ra vì decorator `@tool` từ LangChain **yêu cầu function phải có docstring** hoặc phải cung cấp `description` parameter.

---

## 🔧 SỬA NGAY - FILE `app/services/chatbot_tools.py`

**THAY THẾ TOÀN BỘ:**

```python
"""
CHATBOT TOOLS - Công cụ cho Router Agent
"""

try:
    from langchain.tools import tool
except ImportError:
    try:
        from langchain_core.tools import tool
    except ImportError:
        def tool(func):
            """Fallback decorator"""
            return func

from flask import current_app
from typing import Optional
from datetime import datetime


@tool(description="Tìm kiếm khách sạn và phòng theo yêu cầu của user")
def search_hotels_and_rooms(query: str) -> str:
    """
    Tìm khách sạn và phòng.
    
    Dùng khi user hỏi về:
    - "Tìm phòng ở X"
    - "Khách sạn Y"
    - "Phòng giá Z"
    - "Có WiFi/hồ bơi không"
    
    Args:
        query: Mô tả tìm kiếm
    
    Returns:
        Danh sách phòng phù hợp
    """
    try:
        from app.services.chatbot_service import HotelRAGChatbot
        
        chatbot = HotelRAGChatbot()
        return chatbot.get_answer(query)
        
    except Exception as e:
        current_app.logger.error(f"Search error: {e}")
        return f"Lỗi: {str(e)}"


@tool(description="Lấy danh sách booking của user hiện tại")
def get_my_bookings(user_id: int) -> str:
    """
    Lấy booking của user.
    
    Dùng khi user hỏi về:
    - "Booking của tôi"
    - "Tôi đã đặt phòng nào"
    - "Lịch sử đặt phòng"
    
    Args:
        user_id: ID của user đang đăng nhập
    
    Returns:
        Danh sách booking với thông tin chi tiết
    """
    try:
        from app.models.booking import Booking
        from app.models.booking_detail import BookingDetail
        from app.models.hotel import Hotel
        from app.models.room import Room
        
        bookings = Booking.query.filter_by(
            user_id=user_id
        ).order_by(
            Booking.created_at.desc()
        ).limit(5).all()
        
        if not bookings:
            return "❌ Bạn chưa có booking nào."
        
        result = "📋 **Booking của bạn:**\n\n"
        
        for booking in bookings:
            hotel = Hotel.query.get(booking.hotel_id)
            details = BookingDetail.query.filter_by(
                booking_id=booking.booking_id
            ).all()
            
            rooms = []
            for d in details:
                room = Room.query.get(d.room_id)
                if room:
                    rooms.append(room.room_name)
            
            result += f"""🏨 **{hotel.hotel_name if hotel else 'N/A'}**
📍 {hotel.city if hotel else 'N/A'}
🛏️ {', '.join(rooms) if rooms else 'N/A'}
📅 {booking.check_in_date.strftime('%d/%m/%Y')} → {booking.check_out_date.strftime('%d/%m/%Y')}
💰 {float(booking.final_amount):,.0f}đ
✅ {booking.status} | 💳 {booking.payment_status}

"""
        
        return result.strip()
        
    except Exception as e:
        current_app.logger.error(f"Booking error: {e}")
        return f"Lỗi: {str(e)}"


@tool(description="Xem đánh giá và review của một khách sạn")
def get_hotel_reviews(hotel_name: str) -> str:
    """
    Xem đánh giá khách sạn.
    
    Dùng khi user hỏi:
    - "Review khách sạn X"
    - "Khách sạn Y đánh giá thế nào"
    - "Đánh giá về Z"
    
    Args:
        hotel_name: Tên khách sạn cần xem review
    
    Returns:
        Danh sách reviews và rating trung bình
    """
    try:
        from app.models.hotel import Hotel
        from app.models.review import Review
        from app.models.user import User
        from app import db
        from sqlalchemy import func
        
        hotel = Hotel.query.filter(
            Hotel.hotel_name.ilike(f'%{hotel_name}%'),
            Hotel.status == 'active'
        ).first()
        
        if not hotel:
            return f"❌ Không tìm thấy '{hotel_name}'"
        
        reviews = Review.query.filter_by(
            hotel_id=hotel.hotel_id,
            status='active'
        ).order_by(
            Review.created_at.desc()
        ).limit(5).all()
        
        avg = db.session.query(
            func.avg(Review.rating)
        ).filter_by(
            hotel_id=hotel.hotel_id,
            status='active'
        ).scalar() or 0
        
        result = f"""🏨 **{hotel.hotel_name}**
⭐ Đánh giá: {float(avg):.1f}/5 ({len(reviews)} review)

📝 **Review gần nhất:**

"""
        
        for rev in reviews[:3]:
            user = User.query.get(rev.user_id)
            name = user.full_name if user else "Khách"
            comment = (rev.comment[:80] + "...") if rev.comment and len(rev.comment) > 80 else (rev.comment or "")
            
            result += f"""👤 **{name}** - {rev.rating}⭐
"{comment}"
📅 {rev.created_at.strftime('%d/%m/%Y') if rev.created_at else 'N/A'}

"""
        
        return result.strip()
        
    except Exception as e:
        current_app.logger.error(f"Review error: {e}")
        return f"Lỗi: {str(e)}"


@tool(description="Xem các khuyến mãi đang có hiệu lực")
def get_current_promotions(city: Optional[str] = None) -> str:
    """
    Xem khuyến mãi hiện tại.
    
    Dùng khi user hỏi:
    - "Khuyến mãi gì hiện tại"
    - "Giảm giá ở X"
    - "Có promotion nào không"
    
    Args:
        city: Thành phố (optional, để lọc theo địa điểm)
    
    Returns:
        Danh sách khuyến mãi đang có
    """
    try:
        from app.models.promotion import Promotion
        from app.models.hotel import Hotel
        from app import db
        
        now = datetime.now()
        
        query = db.session.query(Promotion, Hotel).join(
            Hotel, Promotion.hotel_id == Hotel.hotel_id
        ).filter(
            Promotion.is_active == True,
            Promotion.start_date <= now,
            Promotion.end_date >= now,
            Hotel.status == 'active'
        )
        
        if city:
            query = query.filter(Hotel.city.ilike(f'%{city}%'))
        
        promos = query.limit(10).all()
        
        if not promos:
            return "❌ Hiện không có khuyến mãi."
        
        result = "🎁 **Khuyến mãi hiện tại:**\n\n"
        
        for promo, hotel in promos:
            discount = f"{promo.discount_value}%" if promo.discount_type == 'percentage' else f"{promo.discount_value:,.0f}đ"
            
            result += f"""🏨 **{hotel.hotel_name}** ({hotel.city})
💰 {discount} - {promo.title}
📅 Đến {promo.end_date.strftime('%d/%m/%Y')}

"""
        
        return result.strip()
        
    except Exception as e:
        current_app.logger.error(f"Promo error: {e}")
        return f"Lỗi: {str(e)}"


@tool(description="Kiểm tra mã giảm giá còn hiệu lực hay không")
def check_discount_code(code: str) -> str:
    """
    Kiểm tra mã giảm giá.
    
    Dùng khi user hỏi:
    - "Mã ABC còn dùng được không"
    - "Check mã giảm giá XYZ"
    - "Kiểm tra code 123"
    
    Args:
        code: Mã giảm giá cần kiểm tra
    
    Returns:
        Thông tin mã giảm giá (còn hiệu lực hay không)
    """
    try:
        from app.models.discount_code import DiscountCode
        
        now = datetime.now()
        
        discount = DiscountCode.query.filter_by(
            code=code.upper(),
            is_active=True
        ).filter(
            DiscountCode.start_date <= now,
            DiscountCode.end_date >= now
        ).first()
        
        if not discount:
            return f"❌ Mã '{code}' không hợp lệ hoặc hết hạn."
        
        if discount.usage_limit and discount.used_count >= discount.usage_limit:
            return f"❌ Mã '{code}' đã hết lượt sử dụng."
        
        discount_text = f"{discount.discount_value}%" if discount.discount_type == 'percentage' else f"{discount.discount_value:,.0f}đ"
        
        return f"""✅ **Mã '{code}' còn hiệu lực!**

💰 Giảm: {discount_text}
📝 {discount.description or 'Không có mô tả'}
💵 Đơn tối thiểu: {discount.min_order_amount:,.0f}đ
📊 Đã dùng: {discount.used_count}/{discount.usage_limit or '∞'}
📅 Hết hạn: {discount.end_date.strftime('%d/%m/%Y')}"""
        
    except Exception as e:
        current_app.logger.error(f"Discount error: {e}")
        return f"Lỗi: {str(e)}"
```

---

## ✅ GIẢI THÍCH LỖI

**Nguyên nhân:**
```python
@tool  # ❌ Thiếu description parameter
def search_hotels_and_rooms(query: str) -> str:
```

**Sửa:**
```python
@tool(description="Mô tả tool")  # ✅ Có description
def search_hotels_and_rooms(query: str) -> str:
    """Docstring đầy đủ"""  # ✅ Có docstring
```

**LangChain yêu cầu:**
- Hoặc có `description` parameter trong `@tool(description="...")`
- Hoặc function phải có **docstring đầy đủ**
- **Tốt nhất: CẢ HAI** (như code trên)

---

**Restart Flask và test lại nhé!** 🚀