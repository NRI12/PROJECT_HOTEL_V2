// Simple floating chatbot widget for HotelBooking

(function () {
  const userId = window.HOTEL_USER_ID || "guest";
  const STORAGE_KEY = `hotel_chat_history_${userId}`;

  function loadHistory() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return JSON.parse(raw);
    } catch (e) {
      console.error("Cannot read chat history from localStorage", e);
      return [];
    }
  }

  function saveHistory(history) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch (e) {
      console.error("Cannot save chat history to localStorage", e);
    }
  }

  function createWidget() {
    const container = document.createElement("div");
    container.className = "chatbot-widget";
    container.innerHTML = `
      <div class="chatbot-toggle-btn" id="chatbotToggleBtn">
        <i class="bi bi-chat-dots-fill"></i>
      </div>
      <div class="chatbot-window d-none" id="chatbotWindow">
        <div class="chatbot-header">
          <div>
            <strong>Trợ lý HotelBooking</strong>
            <div class="small text-muted">Hỏi mình bất cứ điều gì về đặt phòng</div>
          </div>
          <button type="button" class="btn-close btn-close-white" id="chatbotCloseBtn"></button>
        </div>
        <div class="chatbot-messages" id="chatbotMessages"></div>
        <form class="chatbot-input-area" id="chatbotForm">
          <input
            type="text"
            class="form-control chatbot-input"
            id="chatbotInput"
            placeholder="Nhập câu hỏi của bạn..."
            autocomplete="off"
          />
          <button type="submit" class="btn btn-primary chatbot-send-btn">
            <i class="bi bi-send-fill"></i>
          </button>
        </form>
      </div>
    `;

    document.body.appendChild(container);

    const toggleBtn = document.getElementById("chatbotToggleBtn");
    const closeBtn = document.getElementById("chatbotCloseBtn");
    const windowEl = document.getElementById("chatbotWindow");
    const form = document.getElementById("chatbotForm");
    const input = document.getElementById("chatbotInput");
    const messagesEl = document.getElementById("chatbotMessages");

    function formatMessage(content, role) {
      if (role !== 'assistant') return content;
      
      let formatted = content;
      
      const roomPattern = /(\*\*Phòng \d+:\s*\*\*[^*]+(?:\*\*[^*]+:\*\*[^*]+)*)/g;
      const matches = [...content.matchAll(roomPattern)];
      
      if (matches && matches.length > 0) {
        let lastIndex = 0;
        let result = '';
        
        matches.forEach((match, idx) => {
          const beforeText = content.substring(lastIndex, match.index);
          if (beforeText.trim()) {
            result += beforeText.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
          }
          
          const roomText = match[0];
          const roomNameMatch = roomText.match(/\*\*Phòng \d+:\s*\*\*([^*\n]+)/);
          const roomName = roomNameMatch ? roomNameMatch[1].trim() : '';
          
          const priceMatch = roomText.match(/\*\*Giá:\*\*\s*([^\n*]+)/);
          const price = priceMatch ? priceMatch[1].trim() : '';
          
          const areaMatch = roomText.match(/\*\*Diện tích:\*\*\s*([^\n*]+)/);
          const area = areaMatch ? areaMatch[1].trim() : '';
          
          const guestsMatch = roomText.match(/\*\*Tối đa:\*\*\s*([^\n*]+)/);
          const guests = guestsMatch ? guestsMatch[1].trim() : '';
          
          const bedMatch = roomText.match(/\*\*Giường:\*\*\s*([^\n*]+)/);
          const bed = bedMatch ? bedMatch[1].trim() : '';
          
          const descMatch = roomText.match(/\*\*Mô tả:\*\*\s*([^\n*]+)/);
          const desc = descMatch ? descMatch[1].trim() : '';
          
          const amenitiesMatch = roomText.match(/\*\*Tiện nghi:\*\*\s*([^\n*]+)/);
          const amenities = amenitiesMatch ? amenitiesMatch[1].trim() : '';
          
          result += `
            <div class="chatbot-room-card">
              <div class="chatbot-room-header">
                <i class="bi bi-door-open"></i>
                <strong>${roomName}</strong>
              </div>
              <div class="chatbot-room-details">
                ${price ? `<div class="chatbot-room-item"><i class="bi bi-currency-dollar"></i><span>Giá: <strong>${price}</strong></span></div>` : ''}
                ${area ? `<div class="chatbot-room-item"><i class="bi bi-rulers"></i><span>Diện tích: ${area}</span></div>` : ''}
                ${guests ? `<div class="chatbot-room-item"><i class="bi bi-people"></i><span>Tối đa: ${guests}</span></div>` : ''}
                ${bed ? `<div class="chatbot-room-item"><i class="bi bi-bed"></i><span>Giường: ${bed}</span></div>` : ''}
                ${desc ? `<div class="chatbot-room-desc"><i class="bi bi-info-circle"></i><span>${desc}</span></div>` : ''}
                ${amenities ? `<div class="chatbot-room-amenities"><i class="bi bi-star"></i><span>Tiện nghi: ${amenities}</span></div>` : ''}
              </div>
            </div>
          `;
          
          lastIndex = match.index + match[0].length;
        });
        
        const afterText = content.substring(lastIndex);
        if (afterText.trim()) {
          result += afterText.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
        }
        
        formatted = result;
      } else {
        formatted = formatted
          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          .replace(/\n/g, '<br>');
      }
      
      return formatted;
    }

    function appendMessage(role, content) {
      const msg = document.createElement("div");
      msg.className = `chatbot-message chatbot-message-${role}`;
      
      if (role === 'assistant') {
        const formatted = formatMessage(content, role);
        msg.innerHTML = `<div class="chatbot-bubble">${formatted}</div>`;
      } else {
        msg.innerHTML = `<div class="chatbot-bubble">${content.replace(/\n/g, '<br>')}</div>`;
      }
      
      messagesEl.appendChild(msg);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function showTyping() {
      const typing = document.createElement("div");
      typing.id = "chatbotTyping";
      typing.className = "chatbot-message chatbot-message-assistant";
      typing.innerHTML = `<div class="chatbot-bubble chatbot-typing">
        <span></span><span></span><span></span>
      </div>`;
      messagesEl.appendChild(typing);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function hideTyping() {
      const typing = document.getElementById("chatbotTyping");
      if (typing) typing.remove();
    }

    // Render history
    const history = loadHistory();
    if (!history.length) {
      appendMessage(
        "assistant",
        "Xin chào 👋 Mình là trợ lý ảo của HotelBooking. Bạn cần hỗ trợ tìm khách sạn, khuyến mãi hay đặt phòng không?"
      );
      saveHistory([{ role: "assistant", content: "Xin chào 👋 Mình là trợ lý ảo của HotelBooking. Bạn cần hỗ trợ tìm khách sạn, khuyến mãi hay đặt phòng không?" }]);
    } else {
      history.forEach((m) => appendMessage(m.role, m.content));
    }

    toggleBtn.addEventListener("click", () => {
      windowEl.classList.toggle("d-none");
      if (!windowEl.classList.contains("d-none")) {
        input.focus();
      }
    });

    closeBtn.addEventListener("click", () => {
      windowEl.classList.add("d-none");
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;

      const currentHistory = loadHistory();
      appendMessage("user", text);
      const newHistory = [...currentHistory, { role: "user", content: text }];
      saveHistory(newHistory);
      input.value = "";

      showTyping();

      try {
        const response = await fetch("/api/chatbot/message", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: text,
            history: newHistory,
          }),
        });

        const data = await response.json();
        hideTyping();

        const answer =
          data && data.answer
            ? data.answer
            : "Xin lỗi, hiện mình không thể trả lời yêu cầu này. Vui lòng thử lại sau.";

        appendMessage("assistant", answer);
        const updatedHistory = [...newHistory, { role: "assistant", content: answer }];
        saveHistory(updatedHistory);
      } catch (err) {
        console.error("Chatbot error", err);
        hideTyping();
        const fallback =
          "Đã có lỗi kết nối tới trợ lý. Vui lòng kiểm tra lại mạng hoặc thử lại sau ít phút.";
        appendMessage("assistant", fallback);
        const updatedHistory = [...newHistory, { role: "assistant", content: fallback }];
        saveHistory(updatedHistory);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", createWidget);
  } else {
    createWidget();
  }
})();


