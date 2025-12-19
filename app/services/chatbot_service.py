import os
from typing import List, Dict, Optional

from flask import current_app

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app import db
from app.models.hotel import Hotel
from app.models.room import Room
from app.models.room_type import RoomType
from app.models.amenity import Amenity
from app.models.booking import Booking
from app.models.review import Review
from sqlalchemy import or_, func


def _get_llm() -> ChatOpenAI:
    """
    Khởi tạo LLM từ LangChain, đọc cấu hình từ biến môi trường.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY chưa được cấu hình. "
            "Hãy thêm vào file .env, ví dụ: OPENAI_API_KEY=sk-..."
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    return ChatOpenAI(
        api_key=api_key,
        model=model_name,
        temperature=0.2,
    )


def _search_hotel_by_name(hotel_name: str) -> Optional[Hotel]:
    """
    Tìm kiếm khách sạn theo tên (không phân biệt hoa thường).
    """
    try:
        if not hotel_name or not hotel_name.strip():
            return None
        
        hotel_name_clean = hotel_name.strip()
        
        hotel = Hotel.query.filter(
            Hotel.status == 'active',
            or_(
                Hotel.hotel_name.ilike(f"%{hotel_name_clean}%"),
                Hotel.hotel_name.like(f"%{hotel_name_clean}%")
            )
        ).first()
        
        if not hotel:
            words = hotel_name_clean.split()
            for word in words:
                if len(word) > 2:
                    hotel = Hotel.query.filter(
                        Hotel.status == 'active',
                        Hotel.hotel_name.ilike(f"%{word}%")
                    ).first()
                    if hotel:
                        break
        
        return hotel
    except Exception as exc:
        current_app.logger.error("Lỗi tìm kiếm khách sạn: %s", exc)
        return None


def _get_hotel_rooms_info(hotel: Hotel, limit: int = 50) -> str:
    """
    Lấy thông tin các phòng của khách sạn.
    """
    try:
        rooms = (
            Room.query
            .filter_by(hotel_id=hotel.hotel_id)
            .filter(Room.status.in_(['available', 'occupied']))
            .order_by(Room.base_price.asc())
            .limit(limit)
            .all()
        )
        
        if not rooms:
            return f"\nKhông tìm thấy phòng nào tại {hotel.hotel_name} trong database."
        
        lines = [f"\n=== DANH SÁCH PHÒNG TẠI {hotel.hotel_name.upper()} ==="]
        lines.append(f"Tổng số phòng: {len(rooms)}\n")
        
        for idx, room in enumerate(rooms, 1):
            room_type = room.room_type.type_name if room.room_type else "N/A"
            area_info = f"{float(room.area)}m²" if room.area else ""
            price_info = f"{int(room.base_price):,} VNĐ/đêm" if room.base_price else ""
            guests_info = f"{room.max_guests} người" if room.max_guests else ""
            bed_info = f"{room.num_beds} {room.bed_type or 'giường'}" if room.num_beds else ""
            status_info = f"Trạng thái: {room.status}"
            
            line = f"Phòng {idx}: {room.room_name} (Loại: {room_type})"
            if area_info:
                line += f" | Diện tích: {area_info}"
            if guests_info:
                line += f" | Tối đa: {guests_info}"
            if bed_info:
                line += f" | {bed_info}"
            if price_info:
                line += f" | Giá: {price_info}"
            line += f" | {status_info}"
            
            if room.description:
                line += f"\n  Mô tả: {room.description[:200]}"
            
            amenities = [a.amenity_name for a in room.amenities[:8]]
            if amenities:
                line += f"\n  Tiện nghi: {', '.join(amenities)}"
            
            lines.append(line)
            lines.append("")  # Dòng trống giữa các phòng
        
        return "\n".join(lines)
    except Exception as exc:
        current_app.logger.error("Lỗi lấy thông tin phòng: %s", exc, exc_info=True)
        return ""


def _search_hotels_by_city(city: str, limit: int = 10) -> str:
    """
    Tìm kiếm khách sạn theo thành phố.
    """
    try:
        hotels = (
            Hotel.query
            .filter(
                Hotel.status == 'active',
                or_(
                    Hotel.city.ilike(f"%{city}%"),
                    Hotel.city.like(f"%{city}%")
                )
            )
            .order_by(Hotel.star_rating.desc(), Hotel.hotel_id.desc())
            .limit(limit)
            .all()
        )
        
        if not hotels:
            return ""
        
        lines = [f"\nCác khách sạn tại {city}:"]
        for h in hotels:
            star_info = f"{h.star_rating} sao" if h.star_rating else ""
            line = f"- {h.hotel_name}"
            if star_info:
                line += f" ({star_info})"
            line += f" - {h.address or 'N/A'}"
            lines.append(line)
        
        return "\n".join(lines)
    except Exception as exc:
        current_app.logger.error("Lỗi tìm kiếm khách sạn theo thành phố: %s", exc)
        return ""


def _get_hotel_reviews_info(hotel: Hotel, limit: int = 5) -> str:
    """
    Lấy thông tin đánh giá của khách sạn.
    """
    try:
        reviews = (
            Review.query
            .filter_by(hotel_id=hotel.hotel_id, status='active')
            .order_by(Review.created_at.desc())
            .limit(limit)
            .all()
        )
        
        if not reviews:
            return ""
        
        avg_rating = db.session.query(func.avg(Review.rating)).filter_by(
            hotel_id=hotel.hotel_id, status='active'
        ).scalar() or 0
        
        lines = [f"\nĐánh giá về {hotel.hotel_name}:"]
        lines.append(f"Điểm trung bình: {avg_rating:.1f}/5.0")
        lines.append("Một số đánh giá gần đây:")
        
        for review in reviews:
            line = f"- {review.rating}/5: {review.comment[:100] if review.comment else 'Không có bình luận'}"
            lines.append(line)
        
        return "\n".join(lines)
    except Exception as exc:
        current_app.logger.error("Lỗi lấy đánh giá: %s", exc)
        return ""


def _extract_hotel_name_from_message(message: str) -> List[str]:
    """
    Trích xuất tên khách sạn từ câu hỏi.
    """
    message_lower = message.lower()
    hotel_names = []
    
    all_hotels = Hotel.query.filter_by(status='active').all()
    for hotel in all_hotels:
        hotel_name_lower = hotel.hotel_name.lower()
        words = hotel_name_lower.split()
        for word in words:
            if len(word) > 3 and word in message_lower:
                hotel_names.append(hotel.hotel_name)
                break
    
    if not hotel_names:
        words = message.split()
        potential_names = []
        for i, word in enumerate(words):
            if word[0].isupper() and len(word) > 2:
                name_parts = [word]
                for j in range(i+1, min(i+4, len(words))):
                    if words[j][0].isupper() or words[j].lower() in ['resort', 'hotel', 'inn']:
                        name_parts.append(words[j])
                    else:
                        break
                if len(name_parts) > 1:
                    potential_names.append(' '.join(name_parts))
        
        for name in potential_names:
            hotel = _search_hotel_by_name(name)
            if hotel:
                hotel_names.append(hotel.hotel_name)
    
    return list(set(hotel_names))


def _build_context_from_db(message: str = "") -> str:
    """
    Lấy dữ liệu thực tế từ DB để đưa vào context cho LLM.
    Phân tích câu hỏi và lấy thông tin liên quan từ database.
    """
    context_parts = []
    
    try:
        message_lower = message.lower() if message else ""
        
        room_keywords = ["phòng", "room", "suite", "phòng nào", "có phòng"]
        hotel_keywords = ["khách sạn", "hotel", "resort"]
        city_keywords = ["đà nẵng", "hà nội", "hồ chí minh", "nha trang", "vũng tàu", "danang", "hanoi", "ho chi minh"]
        review_keywords = ["đánh giá", "review", "rating", "sao"]
        
        is_asking_about_room = any(keyword in message_lower for keyword in room_keywords)
        is_asking_about_hotel = any(keyword in message_lower for keyword in hotel_keywords)
        is_asking_about_review = any(keyword in message_lower for keyword in review_keywords)
        
        found_hotel = None
        found_city = None
        
        for city_keyword in city_keywords:
            if city_keyword in message_lower:
                found_city = city_keyword.replace("danang", "Đà Nẵng").replace("hanoi", "Hà Nội").replace("ho chi minh", "Hồ Chí Minh")
                break
        
        hotel_names_from_message = _extract_hotel_name_from_message(message)
        
        for hotel_name in hotel_names_from_message:
            found_hotel = _search_hotel_by_name(hotel_name)
            if found_hotel:
                break
        
        if not found_hotel:
            words = message.split()
            for i in range(len(words)):
                for j in range(i+1, min(i+5, len(words)+1)):
                    potential_name = ' '.join(words[i:j])
                    found_hotel = _search_hotel_by_name(potential_name)
                    if found_hotel:
                        break
                if found_hotel:
                    break
        
        if found_hotel:
            star_info = f"{found_hotel.star_rating} sao" if found_hotel.star_rating else ""
            hotel_info = f"=== THÔNG TIN KHÁCH SẠN {found_hotel.hotel_name.upper()} ==="
            hotel_info += f"\n- Địa điểm: {found_hotel.city or 'N/A'}"
            if star_info:
                hotel_info += f"\n- Hạng: {star_info}"
            hotel_info += f"\n- Địa chỉ: {found_hotel.address or 'N/A'}"
            if found_hotel.description:
                hotel_info += f"\n- Mô tả: {found_hotel.description[:400]}"
            
            context_parts.append(hotel_info)
            
            if is_asking_about_room:
                rooms_info = _get_hotel_rooms_info(found_hotel)
                if rooms_info:
                    context_parts.append(rooms_info)
                else:
                    context_parts.append(f"\nLƯU Ý: Không tìm thấy phòng nào tại {found_hotel.hotel_name} trong database.")
            
            if is_asking_about_review:
                reviews_info = _get_hotel_reviews_info(found_hotel)
                if reviews_info:
                    context_parts.append(reviews_info)
        
        elif found_city:
            city_info = _search_hotels_by_city(found_city)
            if city_info:
                context_parts.append(city_info)
        
        if not context_parts and is_asking_about_room:
            all_hotels = Hotel.query.filter_by(status='active').limit(10).all()
            if all_hotels:
                lines = ["=== DANH SÁCH KHÁCH SẠN CÓ PHÒNG TRONG HỆ THỐNG ==="]
                for h in all_hotels:
                    room_count = Room.query.filter_by(hotel_id=h.hotel_id).count()
                    if room_count > 0:
                        star_info = f"{h.star_rating} sao" if h.star_rating else ""
                        line = f"- {h.hotel_name} tại {h.city or 'N/A'}"
                        if star_info:
                            line += f" ({star_info})"
                        line += f" - Có {room_count} phòng"
                        lines.append(line)
                if len(lines) > 1:
                    context_parts.append("\n".join(lines))
        
    except Exception as exc:
        current_app.logger.error("Lỗi lấy dữ liệu từ DB cho chatbot: %s", exc, exc_info=True)
        return ""
    
    return "\n\n".join(context_parts) if context_parts else ""


def get_chatbot_answer(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Sinh câu trả lời từ chatbot sử dụng LangChain với dữ liệu từ database.
    
    Luồng hoạt động:
    1. Question (câu hỏi từ user)
    2. Phân tích câu hỏi và truy vấn database qua SQLAlchemy
    3. Lấy dữ liệu thực tế từ database
    4. Đưa dữ liệu vào context cho LLM
    5. LLM tạo answer dựa trên dữ liệu thực tế
    6. Display answer cho user
    
    - message: câu hỏi hiện tại của user
    - history: danh sách các message trước đó (không giới hạn)
    """
    llm = _get_llm()

    db_context = _build_context_from_db(message)
    
    system_prompt = (
        "Bạn là trợ lý ảo thông minh cho hệ thống đặt phòng khách sạn HotelBooking.\n"
        "- Trả lời bằng tiếng Việt, giọng điệu thân thiện, ngắn gọn, dễ hiểu.\n"
        "- QUAN TRỌNG: Bạn sẽ nhận được dữ liệu THỰC TẾ từ database bên dưới.\n"
        "- BẮT BUỘC: Bạn PHẢI sử dụng dữ liệu từ database để trả lời, KHÔNG được trả lời chung chung.\n"
        "- Nếu có danh sách phòng từ database, bạn PHẢI liệt kê đầy đủ tất cả các phòng với thông tin chi tiết.\n"
        "- Nếu người dùng hỏi về phòng cụ thể, bạn PHẢI tìm trong danh sách phòng từ database và trả lời.\n"
        "- KHÔNG được nói 'không có thông tin' nếu đã có dữ liệu từ database.\n"
        "- Nếu không có dữ liệu trong database, hãy thông báo rõ ràng.\n"
    )

    if db_context:
        system_prompt += "\n\n=== DỮ LIỆU THỰC TẾ TỪ DATABASE ===\n" + db_context
        system_prompt += "\n\n=== YÊU CẦU ===\n"
        system_prompt += "Bạn PHẢI sử dụng dữ liệu trên để trả lời câu hỏi. "
        system_prompt += "Nếu có danh sách phòng, hãy liệt kê TẤT CẢ các phòng với đầy đủ thông tin (tên, giá, diện tích, tiện nghi, v.v.). "
        system_prompt += "KHÔNG được trả lời chung chung hoặc nói 'không có thông tin' khi đã có dữ liệu từ database."
    else:
        system_prompt += "\n\nLưu ý: Không tìm thấy dữ liệu cụ thể trong database cho câu hỏi này."

    messages: List = [SystemMessage(content=system_prompt)]

    if history:
        for item in history:
            role = item.get("role", "")
            content = item.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=message))

    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as exc:
        current_app.logger.error("Lỗi xử lý chatbot: %s", exc, exc_info=True)
        return "Xin lỗi, có lỗi xảy ra khi xử lý câu hỏi. Vui lòng thử lại sau."
