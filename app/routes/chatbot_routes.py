from flask import Blueprint, request, jsonify, session

from app.services.chatbot_service import get_chatbot_answer

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


@chatbot_bp.route("/message", methods=["POST"])
def chat_message():
    """
    Endpoint nhận message từ frontend và trả về câu trả lời của chatbot.

    Body JSON:
    {
        "message": "câu hỏi",
        "history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        user_id = session.get('user_id')
        
        answer = get_chatbot_answer(message, history, user_id=user_id)
        return jsonify({"answer": answer})
    except Exception as exc:
        from flask import current_app

        current_app.logger.error("Lỗi xử lý chatbot: %s", exc, exc_info=True)
        return (
            jsonify(
                {
                    "error": "Có lỗi xảy ra khi xử lý yêu cầu. Vui lòng thử lại sau.",
                }
            ),
            500,
        )


