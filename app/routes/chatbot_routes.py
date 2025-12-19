from flask import Blueprint, request, jsonify

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
        answer = get_chatbot_answer(message, history)
        return jsonify({"answer": answer})
    except Exception as exc:  # pragma: no cover - tránh lộ lỗi nhạy cảm
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


