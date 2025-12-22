from app import create_app
from app.services.chatbot_service import HotelRAGChatbot


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Initializing vector database...")
        try:
            chatbot = HotelRAGChatbot()
            chatbot.rebuild_vectorstore()
            print("Done!")
            print("Vector DB at: ./chroma_db/")
        except Exception as exc:
            print(f"Error: {exc}")

