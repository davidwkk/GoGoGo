// ChatPage — Main chat UI with AI travel agent

import { useChatStore } from "@/store";
import { InputBar } from "@/components/chat/InputBar";

export function ChatPage() {
  const messages = useChatStore((s) => s.messages);

  return (
    <div className="flex flex-col h-screen">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-muted-foreground text-sm">
              Start a conversation with GoGoGo...
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[70%] rounded-lg px-4 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Input bar */}
      <InputBar />
    </div>
  );
}
