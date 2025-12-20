try:
    from langchain.tools import tool
except ImportError:
    try:
        from langchain_core.tools import tool
    except ImportError:
        def tool(func):
            return func
from flask import current_app
from typing import Optional
from datetime import datetime


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
        from app.models.hotel import Hotel
        from app.models.room import Room
        from app import db
        from sqlalchemy import or_
        
        query_lower = query.lower()
        
        if any(city in query_lower for city in ['đà lạt', 'đà nẵng', 'nha trang', 'hà nội', 'hồ chí minh', 'vũng tàu']):
            found_city = None
            for city in ['đà lạt', 'đà nẵng', 'nha trang', 'hà nội', 'hồ chí minh', 'vũng tàu']:
                if city in query_lower:
                    found_city = city.title()
                    break
            
            hotels = Hotel.query.filter(
                Hotel.status == 'active',
                Hotel.city.ilike(f'%{found_city}%')
            ).limit(5).all()
            
            if hotels:
                result = f"🏨 Khách sạn tại {found_city}:\n\n"
                for h in hotels:
                    result += f"- {h.hotel_name} ({h.star_rating} sao) - {h.address}\n"
                return result
            else:
                return f"Không tìm thấy khách sạn tại {found_city}."
        
        elif any(kw in query_lower for kw in ['giá', 'bao nhiêu', 'triệu', 'tr', 'k']):
            rooms = Room.query.join(Hotel).filter(
                Hotel.status == 'active'
            ).order_by(Room.base_price).limit(5).all()
            
            if rooms:
                result = "💰 Phòng có giá tốt:\n\n"
                for r in rooms:
                    result += f"- {r.room_name} tại {r.hotel.hotel_name}: {int(r.base_price):,}đ/đêm\n"
                return result
            else:
                return "Hiện không có phòng nào."
        
        else:
            hotels = Hotel.query.filter(Hotel.status == 'active').limit(5).all()
            if hotels:
                result = "🏨 Một số khách sạn:\n\n"
                for h in hotels:
                    result += f"- {h.hotel_name} tại {h.city}\n"
                return result
            else:
                return "Hiện không có khách sạn nào."
                
    except Exception as e:
        current_app.logger.error(f"Error in search_hotels_and_rooms: {e}", exc_info=True)
        return f"Lỗi tìm kiếm: {str(e)}"


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
        from app.models.booking import Booking
        from app.models.booking_detail import BookingDetail
        from app.models.hotel import Hotel
        from app.models.room import Room
        from app import db
        
        bookings = Booking.query.filter(
            Booking.user_id == user_id
        ).order_by(
            Booking.created_at.desc()
        ).limit(5).all()
        
        if not bookings:
            return "Bạn chưa có booking nào."
        
        result = "📋 Danh sách booking của bạn:\n\n"
        for booking in bookings:
            hotel = Hotel.query.get(booking.hotel_id)
            booking_details = BookingDetail.query.filter_by(booking_id=booking.booking_id).all()
            
            rooms_info = []
            for bd in booking_details:
                room = Room.query.get(bd.room_id)
                if room:
                    rooms_info.append(room.room_name)
            
            result += f"""
🏨 {hotel.hotel_name if hotel else 'N/A'}
📍 {hotel.city if hotel else 'N/A'}
🛏️ Phòng: {', '.join(rooms_info) if rooms_info else 'N/A'}
📅 Check-in: {booking.check_in_date.strftime('%d/%m/%Y')}
📅 Check-out: {booking.check_out_date.strftime('%d/%m/%Y')}
💰 Tổng: {float(booking.final_amount):,.0f}đ
✅ Trạng thái: {booking.status}
💳 Thanh toán: {booking.payment_status}

"""
        
        return result.strip()
        
    except Exception as e:
        current_app.logger.error(f"Error in get_my_bookings: {e}", exc_info=True)
        return f"Lỗi lấy booking: {str(e)}"


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
            return f"Không tìm thấy khách sạn '{hotel_name}'"
        
        reviews = Review.query.join(
            User, Review.user_id == User.user_id
        ).filter(
            Review.hotel_id == hotel.hotel_id,
            Review.status == 'active'
        ).order_by(
            Review.created_at.desc()
        ).limit(5).all()
        
        avg_rating = db.session.query(
            func.avg(Review.rating)
        ).filter(
            Review.hotel_id == hotel.hotel_id,
            Review.status == 'active'
        ).scalar() or 0
        
        result = f"""
🏨 **{hotel.hotel_name}**
⭐ Đánh giá trung bình: {float(avg_rating):.1f}/5 ({len(reviews)} đánh giá)

📝 Review gần nhất:

"""
        
        for review in reviews[:3]:
            user = User.query.get(review.user_id)
            user_name = user.full_name if user else "Khách"
            comment = review.comment[:100] if review.comment else "Không có bình luận"
            created = review.created_at.strftime('%d/%m/%Y') if review.created_at else "N/A"
            
            result += f"""
👤 {user_name} - ⭐ {review.rating}/5
"{comment}..."
📅 {created}

"""
        
        return result.strip()
        
    except Exception as e:
        current_app.logger.error(f"Error in get_hotel_reviews: {e}", exc_info=True)
        return f"Lỗi lấy review: {str(e)}"


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
        from app.models.promotion import Promotion
        from app.models.hotel import Hotel
        from app import db
        
        now = datetime.now()
        
        query = db.session.query(
            Promotion, Hotel
        ).join(
            Hotel, Promotion.hotel_id == Hotel.hotel_id
        ).filter(
            Promotion.is_active == True,
            Promotion.start_date <= now,
            Promotion.end_date >= now,
            Hotel.status == 'active'
        )
        
        if city:
            query = query.filter(Hotel.city.ilike(f'%{city}%'))
        
        promotions = query.limit(10).all()
        
        if not promotions:
            return "Hiện không có khuyến mãi nào."
        
        result = "🎁 Khuyến mãi hiện tại:\n\n"
        
        for promo, hotel in promotions:
            if promo.discount_type == 'percentage':
                discount = f"Giảm {promo.discount_value}%"
            else:
                discount = f"Giảm {float(promo.discount_value):,.0f}đ"
            
            end_date = promo.end_date.strftime('%d/%m/%Y') if promo.end_date else "N/A"
            
            result += f"""
🏨 {hotel.hotel_name} ({hotel.city})
🎁 {promo.title}
💰 {discount}
📅 Đến: {end_date}

"""
        
        return result.strip()
        
    except Exception as e:
        current_app.logger.error(f"Error in get_current_promotions: {e}", exc_info=True)
        return f"Lỗi lấy khuyến mãi: {str(e)}"


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
        from app.models.discount_code import DiscountCode
        from app import db
        
        now = datetime.now()
        
        discount = DiscountCode.query.filter(
            DiscountCode.code == code.upper(),
            DiscountCode.is_active == True,
            DiscountCode.start_date <= now,
            DiscountCode.end_date >= now
        ).first()
        
        if not discount:
            return f"Mã '{code}' không tồn tại hoặc đã hết hạn."
        
        if discount.usage_limit and discount.used_count >= discount.usage_limit:
            return f"Mã '{code}' đã hết lượt sử dụng."
        
        if discount.discount_type == 'percentage':
            discount_text = f"Giảm {discount.discount_value}%"
        else:
            discount_text = f"Giảm {float(discount.discount_value):,.0f}đ"
        
        end_date = discount.end_date.strftime('%d/%m/%Y') if discount.end_date else "N/A"
        min_order = f"{float(discount.min_order_amount):,.0f}đ" if discount.min_order_amount else "Không có"
        used_info = f"{discount.used_count}/{discount.usage_limit}" if discount.usage_limit else f"{discount.used_count}/∞"
        
        return f"""
✅ Mã '{code}' còn hiệu lực!

💰 Ưu đãi: {discount_text}
📝 Mô tả: {discount.description or 'N/A'}
💵 Đơn tối thiểu: {min_order}
📊 Đã dùng: {used_info}
📅 Hết hạn: {end_date}
"""
        
    except Exception as e:
        current_app.logger.error(f"Error in check_discount_code: {e}", exc_info=True)
        return f"Lỗi kiểm tra mã: {str(e)}"

