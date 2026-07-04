import { type FC, useCallback, useEffect, useRef, useState } from "react";
import { 
  MessageSquare, 
  X, 
  Send, 
  Sparkles, 
  Trash2, 
  Loader2, 
  ChevronUp, 
  ChevronDown,
  Brain,
  Bot,
  GripVertical
} from "lucide-react";
import { parse } from "best-effort-json-parser";

import { useGetAgentList } from "@/api/agent";
import { useGetConversationHistory } from "@/api/conversation";
import { 
  useAgentStore, 
  useConversationById, 
  useAgentStoreActions 
} from "@/store/agent-store";
import useSSE from "@/hooks/use-sse";
import { getServerUrl } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { ChatItem } from "@/types/agent";

import { 
  MarkdownRenderer, 
  ReasoningRenderer, 
  ReportRenderer,
  ToolCallRenderer, 
  UnknownRenderer 
} from "@/components/valuecell/renderer";

export const FloatingChatbot: FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("StrategyAgent");
  const [conversationId, setConversationId] = useState<string>("");
  const [inputValue, setInputValue] = useState("");
  const [isAgentSelectOpen, setIsAgentSelectOpen] = useState(false);
  
  // Draggable states
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [hasDragged, setHasDragged] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const windowRef = useRef<HTMLDivElement>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Get available agents
  const { data: agents = [] } = useGetAgentList({ enabled_only: "true" });
  
  // Get store state and actions
  const curConversation = useConversationById(conversationId);
  const { dispatchAgentStore, dispatchAgentStoreHistory } = useAgentStoreActions();

  // Load saved conversation ID for the selected agent when selectedAgent changes
  useEffect(() => {
    const savedId = localStorage.getItem(`valuecell_chatbot_id_${selectedAgent}`);
    if (savedId) {
      setConversationId(savedId);
    } else {
      setConversationId("");
    }
  }, [selectedAgent]);

  // Fetch history if conversationId is loaded
  const { data: historyData } = useGetConversationHistory(conversationId);

  // Sync conversation history to agentStore
  useEffect(() => {
    if (conversationId && historyData && historyData.length > 0) {
      dispatchAgentStoreHistory(conversationId, historyData, true);
    }
  }, [conversationId, historyData, dispatchAgentStoreHistory]);

  // SSE client setup
  const { connect, close, isStreaming } = useSSE({
    url: getServerUrl("/agents/stream"),
    handlers: {
      onData: (sseData) => {
        dispatchAgentStore(sseData);
        if (sseData.event === "conversation_started") {
          const newId = sseData.data.conversation_id;
          setConversationId(newId);
          localStorage.setItem(`valuecell_chatbot_id_${selectedAgent}`, newId);
        } else if (sseData.event === "done") {
          close();
        } else if (sseData.event === "system_failed") {
          close();
          const errorMsg = sseData.data.payload?.content || "Terjadi kesalahan sistem";
          import("sonner").then(({ toast }) => {
            toast.error(errorMsg);
          }).catch(() => {
            alert(errorMsg);
          });
        }
      },
      onError: (err) => {
        console.error("Chatbot SSE error:", err);
        import("sonner").then(({ toast }) => {
          toast.error("Gagal terhubung ke AI server");
        }).catch(() => {});
      }
    }
  });

  // Automatically scroll to bottom when new messages arrive or drawer opens
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Set initial default position on open (bottom right)
  useEffect(() => {
    if (isOpen && !hasDragged) {
      const defaultLeft = window.innerWidth - 440;
      const defaultTop = window.innerHeight - 684;
      setPosition({
        x: Math.max(10, defaultLeft),
        y: Math.max(10, defaultTop)
      });
    }
    if (isOpen) {
      setTimeout(scrollToBottom, 100);
    }
  }, [isOpen, hasDragged, scrollToBottom]);

  // Handle dragging events
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Left click only
    
    const target = e.target as HTMLElement;
    // Prevent dragging if clicking dropdowns, inputs, buttons
    if (
      target.closest("button") || 
      target.closest("a") || 
      target.closest("input") || 
      target.closest(".relative")
    ) {
      return;
    }
    
    setIsDragging(true);
    setHasDragged(true);
    dragStartRef.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    };
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      
      const newX = e.clientX - dragStartRef.current.x;
      let newY = e.clientY - dragStartRef.current.y;
      
      // Only keep header reachable from top screen boundary
      newY = Math.max(0, newY);
      
      setPosition({ x: newX, y: newY });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  // Flatten nested conversation threads into simple array of items
  const getChatItems = (): ChatItem[] => {
    const items: ChatItem[] = [];
    if (curConversation?.threads) {
      for (const thread of Object.values(curConversation.threads)) {
        for (const task of Object.values(thread.tasks)) {
          if (task.items) {
            items.push(...task.items);
          }
        }
      }
    }
    // Sort items by timestamp or order if they have one (they are processed sequentially by the store reducer)
    return items;
  };

  const chatItems = getChatItems();

  useEffect(() => {
    if (chatItems.length > 0) {
      scrollToBottom();
    }
  }, [chatItems.length, scrollToBottom]);

  // Send message handler
  const handleSend = async () => {
    if (!inputValue.trim() || isStreaming) return;
    const textToSend = inputValue.trim();
    setInputValue("");

    try {
      const request = {
        query: textToSend,
        agent_name: selectedAgent,
        conversation_id: conversationId,
      };

      await connect(JSON.stringify(request));
    } catch (err) {
      console.error("Failed to send chatbot message:", err);
    }
  };

  const handleClearChat = () => {
    if (window.confirm("Hapus riwayat chat untuk agen ini?")) {
      localStorage.removeItem(`valuecell_chatbot_id_${selectedAgent}`);
      setConversationId("");
    }
  };

  const selectedAgentInfo = agents.find(a => a.agent_name === selectedAgent);

  return (
    <>
      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "fixed bottom-6 right-6 z-[9999] p-4 rounded-full flex items-center justify-center cursor-pointer transition-all duration-300 transform hover:scale-105 shadow-lg border",
          isOpen 
            ? "opacity-0 scale-0 pointer-events-none"
            : "bg-slate-900/90 hover:bg-slate-955/90 border-cyan-500/40 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.35)] hover:shadow-[0_0_25px_rgba(6,182,212,0.5)]"
        )}
        title="Tanya AI"
      >
        <MessageSquare className="size-6 animate-pulse" />
      </button>

      {/* Floating Chat Panel */}
      <div
        ref={windowRef}
        style={isOpen ? {
          position: "fixed",
          left: `${position.x}px`,
          top: `${position.y}px`,
          width: "420px",
          height: "600px",
          zIndex: 9998,
        } : {
          display: "none"
        }}
        className={cn(
          "bg-slate-955/95 backdrop-blur-md border border-slate-800/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden transition-shadow duration-300",
          isDragging ? "shadow-cyan-500/10 border-cyan-500/30" : ""
        )}
      >
        {/* Header (Draggable) */}
        <div 
          onMouseDown={handleMouseDown}
          className="p-4 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/40 select-none cursor-grab active:cursor-grabbing flex-shrink-0"
        >
          <div className="flex items-center gap-2 select-none">
            <GripVertical className="size-4 text-slate-500 hover:text-slate-300 cursor-grab active:cursor-grabbing shrink-0" />
            <div className="relative">
              <button
                onClick={() => setIsAgentSelectOpen(!isAgentSelectOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 border border-slate-700 text-sm text-foreground transition-all cursor-pointer"
              >
                <Bot className="size-4 text-cyan-400" />
                <span className="font-semibold text-slate-200">
                  {selectedAgentInfo?.display_name || selectedAgent}
                </span>
                {isAgentSelectOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
              </button>

            {/* Agent Switcher Dropdown */}
            {isAgentSelectOpen && (
              <div className="absolute top-full left-0 mt-1.5 w-64 bg-slate-900 border border-slate-800 rounded-lg shadow-xl py-1 z-[1000] animate-in fade-in slide-in-from-top-1 duration-150">
                {agents.map((agent) => (
                  <button
                    key={agent.agent_name}
                    onClick={() => {
                      setSelectedAgent(agent.agent_name);
                      setIsAgentSelectOpen(false);
                    }}
                    className={cn(
                      "w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between cursor-pointer",
                      selectedAgent === agent.agent_name 
                        ? "bg-cyan-500/10 text-cyan-400 font-medium" 
                        : "text-slate-300 hover:bg-slate-800/50"
                    )}
                  >
                    <span>{agent.display_name}</span>
                    {selectedAgent === agent.agent_name && <Sparkles className="size-3.5 text-cyan-400" />}
                  </button>
                ))}
                {agents.length === 0 && (
                  <div className="px-4 py-2.5 text-xs text-slate-500 italic">
                    Tidak ada agen aktif
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
            {conversationId && (
              <button
                onClick={handleClearChat}
                className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                title="Hapus riwayat chat"
              >
                <Trash2 className="size-4" />
              </button>
            )}
            <button
              onClick={() => setIsOpen(false)}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer"
              title="Tutup Chat"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scroll-container bg-slate-950/20">
          {chatItems.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4">
              <div className="p-4 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 animate-bounce">
                <Bot className="size-8" />
              </div>
              <div className="space-y-1.5">
                <h3 className="font-semibold text-slate-200">
                  Tanya AI {selectedAgentInfo?.display_name || selectedAgent}
                </h3>
                <p className="text-xs text-slate-400 max-w-[280px]">
                  Ketik pertanyaan Anda di bawah untuk mulai menganalisis market atau strategi.
                </p>
              </div>
            </div>
          )}

          {chatItems.map((item) => {
            const isUser = item.role === "user";
            
            return (
              <div
                key={item.item_id}
                className={cn(
                  "flex gap-3 max-w-[85%]",
                  isUser ? "ml-auto flex-row-reverse" : "mr-auto"
                )}
              >
                {/* Avatar */}
                <div className={cn(
                  "size-8 rounded-full flex items-center justify-center text-xs font-bold border shrink-0",
                  isUser 
                    ? "bg-slate-800 border-slate-700 text-slate-300"
                    : "bg-cyan-500/15 border-cyan-500/25 text-cyan-400"
                )}>
                  {isUser ? "U" : <Bot className="size-4" />}
                </div>

                {/* Message Bubble */}
                <div
                  className={cn(
                    "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed text-slate-100",
                    isUser 
                      ? "bg-cyan-600/20 border border-cyan-500/30 rounded-tr-none text-cyan-100" 
                      : "bg-slate-900 border border-slate-800/80 rounded-tl-none"
                  )}
                >
                  {(() => {
                    if (!item.payload) return null;
                    
                    switch (item.component_type) {
                      case "markdown":
                      case "tool_call":
                      case "scheduled_task_controller":
                        return <MarkdownRenderer content={item.payload.content} />;

                      case "reasoning": {
                        const parsed = parse(item.payload.content);
                        return (
                          <ReasoningRenderer
                            content={parsed?.content ?? ""}
                            isComplete={parsed?.isComplete ?? false}
                          />
                        );
                      }

                      case "report":
                        return <ReportRenderer content={item.payload.content} />;

                      default:
                        return (
                          <UnknownRenderer
                            item={item}
                            content={item.payload.content}
                          />
                        );
                    }
                  })()}
                </div>
              </div>
            );
          })}
          
          {/* Typing/Streaming indicator */}
          {isStreaming && (
            <div className="flex gap-3 mr-auto max-w-[85%]">
              <div className="size-8 rounded-full bg-cyan-500/15 border border-cyan-500/25 text-cyan-400 flex items-center justify-center shrink-0">
                <Loader2 className="size-4 animate-spin" />
              </div>
              <div className="bg-slate-900 border border-slate-800/80 rounded-2xl rounded-tl-none px-4 py-3 flex items-center space-x-1.5">
                <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="p-4 border-t border-slate-800/80 bg-slate-900/20 flex gap-2"
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={`Tanya ${selectedAgentInfo?.display_name || selectedAgent}...`}
            disabled={isStreaming}
            className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isStreaming}
            className="p-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white disabled:opacity-50 disabled:bg-slate-800 transition-colors flex items-center justify-center cursor-pointer"
          >
            <Send className="size-4" />
          </button>
        </form>
      </div>
    </>
  );
};
