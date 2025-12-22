from flask import Blueprint, request, jsonify, session

from app.services.chatbot_service import get_chatbot_answer

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


@chatbot_bp.route("/message", methods=["POST"])
def chat_message():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        user_id = session.get("user_id")
        answer = get_chatbot_answer(message, history, user_id=user_id)
        return jsonify({"answer": answer})
    except Exception as exc:
        from flask import current_app
        current_app.logger.error(f"Chatbot error: {exc}", exc_info=True)
        return jsonify({"error": "Có lỗi xảy ra"}), 500


@chatbot_bp.route("/rebuild-vector", methods=["POST"])
def rebuild_vector():
    try:
        from app.services.chatbot_service import HotelRAGChatbot

        chatbot = HotelRAGChatbot()
        chatbot.rebuild_vectorstore()
        return jsonify({"success": True, "message": "Vector DB rebuilt"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


