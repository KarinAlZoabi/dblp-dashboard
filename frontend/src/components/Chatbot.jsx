import { useEffect, useRef, useState } from "react";
import { askRagChat } from "../api/api";


function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [sessionId, setSessionId] = useState(null);

  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text:
        "Hi! I can search the DBLP dataset for publications, authors, topics, and publication years."
    }
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const messagesEndRef = useRef(null);


  // ============================================================
  // AUTO SCROLL
  // ============================================================

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth"
    });
  }, [messages, loading]);


  // ============================================================
  // SEND MESSAGE
  // ============================================================

  const sendMessage = async (question = input) => {
    const cleanedQuestion = question.trim();

    if (!cleanedQuestion || loading) {
      return;
    }

    const userMessage = {
      role: "user",
      text: cleanedQuestion
    };

    setMessages((previous) => [
      ...previous,
      userMessage
    ]);

    setInput("");
    setLoading(true);

    try {
      const response = await askRagChat(
  cleanedQuestion,
  5,
  sessionId
);

const data = response.data;

if (data.session_id) {
  setSessionId(data.session_id);
}

      const assistantMessage = {
        role: "assistant",
        text: data.answer,
        sources: data.sources || []
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage
      ]);
    } catch (error) {
      console.error(
        "RAG chatbot error:",
        error
      );

      let message =
        "Something went wrong while searching DBLP.";

      if (error.response?.status === 500) {
        message =
          "The AI service is temporarily unavailable. Please try again.";
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          text: message,
          error: true
        }
      ]);
    } finally {
      setLoading(false);
    }
  };


  // ============================================================
  // KEYBOARD
  // ============================================================

  const handleKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  };


  // ============================================================
  // DBLP LINK
  // ============================================================

  const getDblpUrl = (key) => {
    return `https://dblp.org/rec/${key}.html`;
  };


  // ============================================================
  // UI
  // ============================================================

  return (
    <>
      {/* FLOATING BUTTON */}

      {!isOpen && (
        <button
          className="chatbot-launcher"
          onClick={() => setIsOpen(true)}
          aria-label="Open DBLP assistant"
        >
          <span className="chatbot-launcher-icon">
            ✦
          </span>

          <span className="chatbot-launcher-text">
            Ask DBLP
          </span>
        </button>
      )}


      {/* CHAT WINDOW */}

      {isOpen && (
        <div className="chatbot-panel">

          {/* HEADER */}

          <div className="chatbot-header">

            <div className="chatbot-header-info">

              <div className="chatbot-avatar">
                ✦
              </div>

              <div>
                <h3>DBLP Research Assistant</h3>

                <p>
                  Hybrid RAG search
                </p>
              </div>

            </div>


            <button
              className="chatbot-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close chatbot"
            >
              ×
            </button>

          </div>


          {/* MESSAGES */}

          <div className="chatbot-messages">

            {messages.map((message, index) => (
              <div
                key={index}
                className={`chat-message ${
                  message.role === "user"
                    ? "chat-message-user"
                    : "chat-message-assistant"
                }`}
              >

                <div
                  className={`chat-bubble ${
                    message.error
                      ? "chat-bubble-error"
                      : ""
                  }`}
                >
                  {message.text}
                </div>


                {/* SOURCES */}

                {message.sources?.length > 0 && (
                  <div className="chat-sources">

                    <span className="chat-sources-label">
                      DBLP sources
                    </span>

                    {message.sources.map(
                      (source) => (
                        <a
                          key={source.id}
                          className="chat-source-card"
                          href={getDblpUrl(
                            source.key
                          )}
                          target="_blank"
                          rel="noreferrer"
                        >

                          <div className="chat-source-top">

                            <span className="chat-source-id">
                              {source.id}
                            </span>

                            <span className="chat-source-year">
                              {source.year || "—"}
                            </span>

                          </div>

                          <strong>
                            {source.title}
                          </strong>

                          <span className="chat-source-authors">
                            {source.authors?.length
                              ? source.authors.join(
                                  ", "
                                )
                              : "Author unavailable"}
                          </span>

                          <span className="chat-source-meta">
                            {source.venue ||
                              "Venue unavailable"}

                            {source.type
                              ? ` · ${source.type}`
                              : ""}
                          </span>

                        </a>
                      )
                    )}

                  </div>
                )}

              </div>
            ))}


            {/* LOADING */}

            {loading && (
              <div className="chat-message chat-message-assistant">

                <div className="chat-loading">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>

                <small>
                  Searching 12.9M DBLP records...
                </small>

              </div>
            )}


            <div ref={messagesEndRef} />

          </div>


          {/* EXAMPLE QUESTIONS */}

          {messages.length === 1 && (
            <div className="chat-suggestions">

              <button
                onClick={() =>
                  sendMessage(
                    "Find papers about federated learning from 2020 to 2023"
                  )
                }
              >
                Federated learning 2020–2023
              </button>

              <button
                onClick={() =>
                  sendMessage(
                    "Find papers about network intrusion detection"
                  )
                }
              >
                Network intrusion detection
              </button>

              <button
                onClick={() =>
                  sendMessage(
                    "Find Attention Is All You Need"
                  )
                }
              >
                Attention Is All You Need
              </button>

            </div>
          )}


          {/* INPUT */}

          <div className="chatbot-input-area">

            <textarea
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Ask about DBLP publications..."
              rows={1}
              disabled={loading}
            />

            <button
              className="chatbot-send"
              onClick={() => sendMessage()}
              disabled={
                loading ||
                !input.trim()
              }
              aria-label="Send message"
            >
              ↑
            </button>

          </div>

        </div>
      )}
    </>
  );
}


export default Chatbot;