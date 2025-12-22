from __future__ import annotations

import os
from typing import Dict, List, Optional

from flask import current_app

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.schema.output_parser import StrOutputParser
    from langchain.schema.runnable import RunnablePassthrough

    try:
        from langchain_core.messages import AIMessage, HumanMessage
    except Exception:
        from langchain.schema import AIMessage, HumanMessage

    LANGCHAIN_AVAILABLE = True
except Exception:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None
    OpenAIEmbeddings = None
    Chroma = None
    AgentExecutor = None
    create_openai_functions_agent = None
    ChatPromptTemplate = None
    MessagesPlaceholder = None
    StrOutputParser = None
    RunnablePassthrough = None
    HumanMessage = None
    AIMessage = None

try:
    from openai import RateLimitError
except Exception:
    RateLimitError = Exception

from app.services.chatbot_cache import get_cached_answer, save_to_cache


class HotelRAGChatbot:
    _instance = None
    _vectorstore = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return

        if not LANGCHAIN_AVAILABLE:
            current_app.logger.warning("LangChain not available")
            self.initialized = False
            return

        self.api_key = current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.initialized = False
            return

        self.embeddings = OpenAIEmbeddings(api_key=self.api_key, model="text-embedding-3-small")
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=self.api_key,
            request_timeout=15,
        )

        self.initialized = True
        self._load_or_create_vectorstore()

    def _load_or_create_vectorstore(self):
        persist_dir = "./chroma_db"
        try:
            if os.path.exists(persist_dir):
                HotelRAGChatbot._vectorstore = Chroma(
                    persist_directory=persist_dir,
                    embedding_function=self.embeddings,
                )
                current_app.logger.info("Vector DB loaded")
            else:
                current_app.logger.info("Vector DB not found - using SQL fallback")
        except Exception as exc:
            current_app.logger.warning(f"Load vector DB failed: {exc}")

    def get_answer(self, query: str) -> str:
        if not self.initialized or not HotelRAGChatbot._vectorstore:
            return self._sql_fallback(query)

        try:
            retriever = HotelRAGChatbot._vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 5},
            )

            template = """
Bạn là trợ lý tìm phòng khách sạn.

THÔNG TIN PHÒNG:
{context}

CÂU HỎI: {question}

TRẢ LỜI:
- Format đẹp với emoji (🏨 📍 💰 👥 ⭐)
- Giới thiệu 3-5 phòng phù hợp
- Ngắn gọn, dễ đọc
- Kết thúc bằng câu hỏi gợi ý

Trả lời:"""

            prompt = ChatPromptTemplate.from_template(template)

            def format_docs(docs):
                return "\n\n---\n\n".join([d.page_content for d in docs])

            chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )

            answer = chain.invoke(query)
            return (answer or "").strip()
        except Exception as exc:
            current_app.logger.error(f"RAG error: {exc}")
            return self._sql_fallback(query)

    def _sql_fallback(self, query: str) -> str:
        from app.models.hotel import Hotel

        msg = (query or "").lower()

        cities = {
            "đà lạt": "Đà Lạt",
            "đà nẵng": "Đà Nẵng",
            "nha trang": "Nha Trang",
            "hà nội": "Hà Nội",
            "hồ chí minh": "TP.HCM",
            "vũng tàu": "Vũng Tàu",
            "phú quốc": "Phú Quốc",
            "huế": "Huế",
        }

        found_city = None
        for key, value in cities.items():
            if key in msg:
                found_city = value
                break

        if found_city:
            hotels = (
                Hotel.query.filter(
                    Hotel.status == "active",
                    Hotel.city.ilike(f"%{found_city}%"),
                )
                .limit(3)
                .all()
            )

            if hotels:
                result = f"🏨 **Khách sạn tại {found_city}:**\n\n"
                for h in hotels:
                    result += f"• **{h.hotel_name}** ({h.star_rating}⭐)\n"
                    result += f"  📍 {h.address}\n\n"
                result += "Bạn muốn xem chi tiết phòng nào?"
                return result

        return "Bạn muốn tìm phòng ở đâu? (VD: Đà Lạt, Nha Trang, Đà Nẵng...)"

    def rebuild_vectorstore(self):
        from sqlalchemy import func

        from app import db
        from app.models.amenity import Amenity
        from app.models.hotel import Hotel
        from app.models.hotel_amenity import hotel_amenities
        from app.models.review import Review
        from app.models.room import Room
        from app.models.room_amenity import room_amenities
        from app.models.room_type import RoomType

        import shutil

        if os.path.exists("./chroma_db"):
            shutil.rmtree("./chroma_db")

        current_app.logger.info("Rebuilding vector DB...")

        results = (
            db.session.query(Hotel, Room, RoomType)
            .join(Room, Hotel.hotel_id == Room.hotel_id)
            .join(RoomType, Room.room_type_id == RoomType.type_id)
            .filter(
                Hotel.status == "active",
                Room.status == "available",
            )
            .all()
        )

        if not results:
            raise RuntimeError("No hotel data")

        documents = []
        metadatas = []
        ids = []

        for hotel, room, room_type in results:
            hotel_amen = (
                db.session.query(Amenity)
                .join(hotel_amenities)
                .filter(hotel_amenities.c.hotel_id == hotel.hotel_id)
                .all()
            )

            room_amen = (
                db.session.query(Amenity)
                .join(room_amenities)
                .filter(room_amenities.c.room_id == room.room_id)
                .all()
            )

            avg_rating = (
                db.session.query(func.avg(Review.rating))
                .filter(Review.hotel_id == hotel.hotel_id)
                .scalar()
                or 0
            )

            base_price = float(room.base_price or 0)
            weekend_price = float(room.weekend_price) if room.weekend_price is not None else base_price
            area_text = f"{float(room.area):g}" if room.area is not None else "N/A"

            doc = f"""
🏨 {hotel.hotel_name}
⭐ {hotel.star_rating} sao | 📊 {avg_rating:.1f}/5
📍 {hotel.city}, {hotel.address}

🛏️ {room_type.type_name} - {room.room_name}
💰 Giá: {base_price:,.0f}đ (thường) / {weekend_price:,.0f}đ (cuối tuần)
👥 Tối đa {room.max_guests} người
📏 {area_text}m²

✨ Tiện nghi khách sạn: {", ".join([a.amenity_name for a in hotel_amen]) or "Không có"}
✨ Tiện nghi phòng: {", ".join([a.amenity_name for a in room_amen]) or "Không có"}
            """.strip()

            documents.append(doc)
            metadatas.append(
                {
                    "hotel_id": hotel.hotel_id,
                    "hotel_name": hotel.hotel_name,
                    "city": hotel.city,
                    "room_id": room.room_id,
                    "room_name": room.room_name,
                    "base_price": float(room.base_price),
                    "max_guests": room.max_guests,
                }
            )
            ids.append(f"h{hotel.hotel_id}_r{room.room_id}")

        HotelRAGChatbot._vectorstore = Chroma.from_texts(
            texts=documents,
            embedding=self.embeddings,
            metadatas=metadatas,
            ids=ids,
            persist_directory="./chroma_db",
        )

        current_app.logger.info(f"Vector DB created: {len(documents)} rooms")


def get_chatbot_answer(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[int] = None,
) -> str:
    cached = get_cached_answer(message)
    if cached:
        current_app.logger.info("Cache hit")
        return cached

    try:
        if not LANGCHAIN_AVAILABLE:
            return _direct_tool_call(message, user_id)

        api_key = current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "⚠️ Hệ thống chưa cấu hình OpenAI API"

        from app.services.chatbot_tools import (
            check_discount_code,
            get_current_promotions,
            get_hotel_reviews,
            get_my_bookings,
            search_hotels_and_rooms,
            tool,
        )

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=api_key,
            request_timeout=15,
        )

        tools = [
            search_hotels_and_rooms,
            get_hotel_reviews,
            get_current_promotions,
            check_discount_code,
        ]

        if user_id:
            @tool
            def get_my_bookings_tool(_: str = "") -> str:
                """
                Lấy danh sách booking của user hiện tại.

                Returns:
                    Danh sách booking của user.
                """
                return get_my_bookings.invoke({"user_id": user_id})

            tools.append(get_my_bookings_tool)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Bạn là trợ lý đặt phòng khách sạn thông minh.

CÔNG CỤ:
1. search_hotels_and_rooms - Tìm phòng/khách sạn
2. get_hotel_reviews - Xem đánh giá
3. get_current_promotions - Xem khuyến mãi
4. check_discount_code - Kiểm tra mã
5. get_my_bookings_tool - Xem booking (nếu đã đăng nhập)

NHIỆM VỤ:
- Phân tích câu hỏi
- Chọn công cụ phù hợp
- Trả lời tự nhiên bằng tiếng Việt

VÍ DỤ:
"Tìm phòng Đà Lạt" → search_hotels_and_rooms
"Review Sunrise" → get_hotel_reviews
"Booking của tôi" → get_my_bookings_tool
"Mã SUMMER500" → check_discount_code""",
                ),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

        agent = create_openai_functions_agent(llm=llm, tools=tools, prompt=prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=3,
            max_execution_time=15,
            handle_parsing_errors=True,
        )

        chat_history = []
        if history:
            for item in history[-5:]:
                role = item.get("role")
                content = item.get("content", "")
                if role == "user":
                    chat_history.append(HumanMessage(content=content))
                elif role == "assistant":
                    chat_history.append(AIMessage(content=content))

        response = agent_executor.invoke({"input": message, "chat_history": chat_history})
        answer = (response or {}).get("output", "") or ""

        if answer:
            save_to_cache(message, answer)
            return answer

        return _direct_tool_call(message, user_id)
    except RateLimitError:
        return "⏱️ Hệ thống đang bận. Vui lòng chờ 10s và thử lại."
    except Exception as exc:
        current_app.logger.error(f"Chatbot error: {exc}", exc_info=True)
        return _direct_tool_call(message, user_id)


def _direct_tool_call(message: str, user_id: Optional[int] = None) -> str:
    from app.services.chatbot_tools import (
        check_discount_code,
        get_current_promotions,
        get_hotel_reviews,
        get_my_bookings,
        search_hotels_and_rooms,
    )

    msg = (message or "").lower()

    if user_id and any(kw in msg for kw in ["booking", "đặt phòng", "lịch sử"]):
        return get_my_bookings.invoke({"user_id": user_id})

    if any(kw in msg for kw in ["review", "đánh giá", "sao"]):
        for word in (message or "").split():
            if len(word) > 3:
                return get_hotel_reviews.invoke({"hotel_name": word})

    if any(kw in msg for kw in ["khuyến mãi", "giảm giá", "promo"]):
        return get_current_promotions.invoke({})

    for word in (message or "").split():
        if len(word) >= 5 and word.isupper():
            return check_discount_code.invoke({"code": word})

    return search_hotels_and_rooms.invoke({"query": message})

