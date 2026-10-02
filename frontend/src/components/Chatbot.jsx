import { useEffect, useMemo, useRef, useState } from "react";
import { askRagChat } from "../api/api";
import "./Chatbot.css";

const WELCOME_MESSAGE = {
  id: "welcome",
  role: "assistant",
  text:
    "Hi! I’m your DBLP research assistant. Ask me about papers, authors, publication years, venues, co-authors, or research topics.",
  sources: []
};

const SUGGESTIONS = [
  "Find federated learning papers from 2020 to 2023",
  "Who wrote 'Attention Is All You Need'?",
  "What are Kassem Danach's most recent publications?"
];

const LOADING_STAGES = [
  "Understanding your question…",
  "Searching DBLP…",
  "Preparing the answer…"
];

function FullscreenIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M21 16v5h-5" />
    </svg>
  );
}

function MinimizeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 3v5H3M16 3v5h5M8 21v-5H3M16 21v-5h5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

function NewChatIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 4l16 8-16 8 3-8-3-8Z" />
      <path d="M7 12h13" />
    </svg>
  );
}

function ChevronIcon({ open }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={open ? "chat-chevron-open" : ""}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function ExternalIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14 5h5v5M19 5l-8 8" />
      <path d="M19 13v6H5V5h6" />
    </svg>
  );
}

function formatType(type) {
  const normalized = (type || "").toLowerCase();

  if (normalized === "inproceedings") return "Conference paper";
  if (normalized === "article") return "Article";
  if (normalized === "proceedings") return "Proceedings";
  if (normalized === "phdthesis") return "PhD thesis";
  if (normalized === "mastersthesis") return "Master's thesis";
  if (normalized === "incollection") return "Book chapter";
  if (normalized === "book") return "Book";

  return type || "Publication";
}

function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(0);
  const [expandedSources, setExpandedSources] = useState({});
  const [visibleSourceCounts, setVisibleSourceCounts] = useState({});

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const sessionIdRef = useRef(null);
  const messageCounterRef = useRef(0);

  const loadingText = useMemo(() => {
    if (!loading) return "";
    return LOADING_STAGES[
      Math.min(loadingStage, LOADING_STAGES.length - 1)
    ];
  }, [loading, loadingStage]);

  const nextMessageId = () => {
    messageCounterRef.current += 1;
    return `message-${Date.now()}-${messageCounterRef.current}`;
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end"
    });
  }, [messages, loading, expandedSources]);

  useEffect(() => {
    if (!loading) {
      setLoadingStage(0);
      return;
    }

    setLoadingStage(0);

    const first = window.setTimeout(
      () => setLoadingStage(1),
      900
    );

    const second = window.setTimeout(
      () => setLoadingStage(2),
      2500
    );

    return () => {
      window.clearTimeout(first);
      window.clearTimeout(second);
    };
  }, [loading]);

  useEffect(() => {
    if (!isFullscreen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isFullscreen]);

  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key !== "Escape") return;

      if (isFullscreen) {
        setIsFullscreen(false);
        return;
      }

      if (isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("keydown", handleEscape);
    };
  }, [isFullscreen, isOpen]);

  useEffect(() => {
    if (isOpen) {
      window.setTimeout(() => {
        textareaRef.current?.focus();
      }, 100);
    }
  }, [isOpen, isFullscreen]);

  const startNewChat = () => {
    sessionIdRef.current = null;
    setMessages([WELCOME_MESSAGE]);
    setExpandedSources({});
    setVisibleSourceCounts({});
    setInput("");

    window.setTimeout(() => {
      textareaRef.current?.focus();
    }, 50);
  };

  const sendMessage = async (question = input) => {
    const cleanedQuestion = question.trim();

    if (!cleanedQuestion || loading) return;

    const userMessage = {
      id: nextMessageId(),
      role: "user",
      text: cleanedQuestion,
      sources: []
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
        sessionIdRef.current
      );

      const data = response.data;

      if (data.session_id) {
        sessionIdRef.current = data.session_id;
      }

      const assistantMessage = {
        id: nextMessageId(),
        role: "assistant",
        text:
          data.answer ||
          "I found the DBLP results, but there was no answer text to display.",
        sources: data.sources || [],
        intent: data.intent,
        count: data.count
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage
      ]);
    } catch (error) {
      console.error("DBLP chatbot error:", error);

      let message =
        "I couldn’t complete that DBLP request. Please try again.";

      if (!error.response) {
        message =
          "I can’t reach the DBLP backend right now. Make sure the server is running and try again.";
      } else if (error.response?.status >= 500) {
        message =
          "The DBLP service hit a temporary problem. Your chat is still here — please try that question again.";
      }

      setMessages((previous) => [
        ...previous,
        {
          id: nextMessageId(),
          role: "assistant",
          text: message,
          error: true,
          sources: []
        }
      ]);
    } finally {
      setLoading(false);

      window.setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
    }
  };

  const handleKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  };

  const toggleSources = (messageId) => {
    setExpandedSources((previous) => ({
      ...previous,
      [messageId]: !previous[messageId]
    }));

    setVisibleSourceCounts((previous) => ({
      ...previous,
      [messageId]: previous[messageId] || 5
    }));
  };

  const showMoreSources = (messageId, total) => {
    setVisibleSourceCounts((previous) => ({
      ...previous,
      [messageId]: Math.min(
        (previous[messageId] || 5) + 5,
        total
      )
    }));
  };

  const getDblpUrl = (key) => {
    return `https://dblp.org/rec/${key}.html`;
  };

  const openCitation = (messageId, sourceId) => {
    setExpandedSources((previous) => ({
      ...previous,
      [messageId]: true
    }));

    window.setTimeout(() => {
      document
        .getElementById(`${messageId}-${sourceId}`)
        ?.scrollIntoView({
          behavior: "smooth",
          block: "nearest"
        });
    }, 50);
  };

  const renderInlineAnswer = (
    text,
    sources,
    messageId,
    keyPrefix
  ) => {
    const sourceIds = new Set(
      (sources || []).map((source) => source.id)
    );

    const pieces = text.split(
      /(\[P\d+\]|\*\*[^*\n]+\*\*)/g
    );

    return pieces.map((piece, index) => {
      const citationMatch = piece.match(
        /^\[(P\d+)\]$/
      );

      if (citationMatch) {
        const sourceId = citationMatch[1];

        if (!sourceIds.has(sourceId)) {
          return (
            <span key={`${keyPrefix}-citation-${index}`}>
              {piece}
            </span>
          );
        }

        return (
          <button
            key={`${keyPrefix}-citation-${index}`}
            type="button"
            className="chat-inline-citation"
            onClick={() =>
              openCitation(messageId, sourceId)
            }
            title={`Show source ${sourceId}`}
          >
            {sourceId}
          </button>
        );
      }

      const boldMatch = piece.match(
        /^\*\*(.+)\*\*$/
      );

      if (boldMatch) {
        return (
          <strong key={`${keyPrefix}-bold-${index}`}>
            {boldMatch[1]}
          </strong>
        );
      }

      return (
        <span key={`${keyPrefix}-text-${index}`}>
          {piece}
        </span>
      );
    });
  };


  const renderAnswer = (
    text,
    sources,
    messageId
  ) => {
    if (!text) return null;

    const normalized = text
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n");

    const lines = normalized.split("\n");
    const blocks = [];
    let paragraphLines = [];
    let bulletItems = [];

    const flushParagraph = () => {
      if (!paragraphLines.length) return;

      const value = paragraphLines
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();

      if (value) {
        blocks.push({
          type: "paragraph",
          value
        });
      }

      paragraphLines = [];
    };

    const flushBullets = () => {
      if (!bulletItems.length) return;

      blocks.push({
        type: "list",
        items: bulletItems
      });

      bulletItems = [];
    };

    lines.forEach((line) => {
      const bulletMatch = line.match(
        /^\s*[-*•]\s+(.+)$/
      );

      if (bulletMatch) {
        flushParagraph();
        bulletItems.push(
          bulletMatch[1].trim()
        );
        return;
      }

      if (!line.trim()) {
        flushParagraph();
        flushBullets();
        return;
      }

      if (bulletItems.length) {
        flushBullets();
      }

      paragraphLines.push(
        line.trim()
      );
    });

    flushParagraph();
    flushBullets();

    return (
      <div className="chat-answer-content">
        {blocks.map((block, blockIndex) => {
          if (block.type === "list") {
            return (
              <ul
                key={`${messageId}-list-${blockIndex}`}
                className="chat-answer-list"
              >
                {block.items.map((item, itemIndex) => (
                  <li
                    key={`${messageId}-list-${blockIndex}-${itemIndex}`}
                  >
                    {renderInlineAnswer(
                      item,
                      sources,
                      messageId,
                      `${messageId}-list-${blockIndex}-${itemIndex}`
                    )}
                  </li>
                ))}
              </ul>
            );
          }

          return (
            <p
              key={`${messageId}-paragraph-${blockIndex}`}
              className="chat-answer-paragraph"
            >
              {renderInlineAnswer(
                block.value,
                sources,
                messageId,
                `${messageId}-paragraph-${blockIndex}`
              )}
            </p>
          );
        })}
      </div>
    );
  };

  return (
    <>
      {!isOpen && (
        <button
          className="chatbot-launcher"
          onClick={() => setIsOpen(true)}
          aria-label="Open DBLP research assistant"
        >
          <span className="chatbot-launcher-icon">✦</span>
          <span className="chatbot-launcher-text">Ask DBLP</span>
        </button>
      )}

      {isOpen && (
        <section
          className={`chatbot-panel ${
            isFullscreen
              ? "chatbot-panel-fullscreen"
              : ""
          }`}
          aria-label="DBLP Research Assistant"
        >

          <header className="chatbot-header">

            <div className="chatbot-header-info">
              <div className="chatbot-avatar">✦</div>

              <div className="chatbot-header-copy">
                <h3>DBLP Research Assistant</h3>

                <div className="chatbot-status">
                  <span className="chatbot-status-dot" />
                  DBLP index ready
                </div>
              </div>
            </div>

            <div className="chatbot-header-actions">

              <button
                type="button"
                className="chatbot-icon-button"
                onClick={startNewChat}
                title="Start a new chat"
                aria-label="Start a new chat"
              >
                <NewChatIcon />
              </button>

              <button
                type="button"
                className="chatbot-icon-button"
                onClick={() =>
                  setIsFullscreen((value) => !value)
                }
                title={
                  isFullscreen
                    ? "Exit full screen"
                    : "Open full screen"
                }
                aria-label={
                  isFullscreen
                    ? "Exit full screen"
                    : "Open chatbot full screen"
                }
              >
                {isFullscreen
                  ? <MinimizeIcon />
                  : <FullscreenIcon />}
              </button>

              <button
                type="button"
                className="chatbot-icon-button"
                onClick={() => {
                  setIsFullscreen(false);
                  setIsOpen(false);
                }}
                title="Close"
                aria-label="Close chatbot"
              >
                <CloseIcon />
              </button>

            </div>

          </header>

          <div className="chatbot-messages">

            <div className="chatbot-context-note">
              Ask naturally — you can follow up with things like
              “what about 2023?” or “who wrote the second one?”
            </div>

            {messages.map((message) => {
              const sourcesOpen =
                !!expandedSources[message.id];

              const visibleSourceCount =
                visibleSourceCounts[message.id] || 5;

              const visibleSources =
                message.sources?.slice(0, visibleSourceCount) || [];

              return (
                <article
                  key={message.id}
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
                    {renderAnswer(
                      message.text,
                      message.sources,
                      message.id
                    )}
                  </div>

                  {message.sources?.length > 0 && (
                    <div className="chat-source-section">

                      <button
                        type="button"
                        className="chat-source-toggle"
                        onClick={() =>
                          toggleSources(message.id)
                        }
                        aria-expanded={sourcesOpen}
                      >
                        <span>
                          {message.sources.length}{" "}
                          {message.sources.length === 1
                            ? "DBLP source"
                            : "DBLP sources"}
                        </span>

                        <ChevronIcon open={sourcesOpen} />
                      </button>

                      {sourcesOpen && (
                        <div className="chat-sources">

                          {visibleSources.map(
                            (source) => (
                              <a
                                id={`${message.id}-${source.id}`}
                                key={source.id}
                                className="chat-source-card"
                                href={getDblpUrl(source.key)}
                                target="_blank"
                                rel="noreferrer"
                              >

                                <div className="chat-source-top">

                                  <span className="chat-source-id">
                                    {source.id}
                                  </span>

                                  <div className="chat-source-badges">

                                    {source.year && (
                                      <span className="chat-source-badge">
                                        {source.year}
                                      </span>
                                    )}

                                    <span className="chat-source-badge">
                                      {formatType(source.type)}
                                    </span>

                                  </div>

                                </div>

                                <strong className="chat-source-title">
                                  {source.title}
                                </strong>

                                <span className="chat-source-authors">
                                  {source.authors?.length
                                    ? source.authors.join(", ")
                                    : "Author unavailable"}
                                </span>

                                <div className="chat-source-footer">

                                  <span>
                                    {source.venue ||
                                      "Venue unavailable"}
                                  </span>

                                  <span className="chat-source-open">
                                    Open DBLP
                                    <ExternalIcon />
                                  </span>

                                </div>

                              </a>
                            )
                          )}

                          {visibleSourceCount < message.sources.length && (
                            <button
                              type="button"
                              className="chat-source-more"
                              onClick={() =>
                                showMoreSources(
                                  message.id,
                                  message.sources.length
                                )
                              }
                            >
                              Show 5 more
                              <span>
                                {message.sources.length - visibleSourceCount} remaining
                              </span>
                            </button>
                          )}

                        </div>
                      )}

                    </div>
                  )}

                </article>
              );
            })}

            {loading && (
              <article
                className="chat-message chat-message-assistant"
                aria-live="polite"
              >

                <div className="chat-loading-card">

                  <div className="chat-loading-spinner">
                    <span />
                    <span />
                    <span />
                  </div>

                  <div>
                    <strong>{loadingText}</strong>

                    <span>
                      Semantic searches may take a few seconds.
                    </span>
                  </div>

                </div>

              </article>
            )}

            <div ref={messagesEndRef} />
          </div>

          {messages.length === 1 && !loading && (
            <div className="chat-suggestions">

              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => sendMessage(suggestion)}
                >
                  {suggestion}
                </button>
              ))}

            </div>
          )}

          <footer className="chatbot-input-area">

            <div className="chatbot-composer">

              <textarea
                ref={textareaRef}
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                onKeyDown={handleKeyDown}
                placeholder="Ask anything about DBLP…"
                rows={1}
                disabled={loading}
              />

              <button
                type="button"
                className="chatbot-send"
                onClick={() => sendMessage()}
                disabled={
                  loading ||
                  !input.trim()
                }
                aria-label="Send message"
              >
                <SendIcon />
              </button>

            </div>

            <div className="chatbot-input-hint">
              Enter to send · Shift + Enter for a new line
              {isFullscreen && " · Esc to exit full screen"}
            </div>

          </footer>

        </section>
      )}
    </>
  );
}

export default Chatbot;
