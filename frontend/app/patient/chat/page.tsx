"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { Message, RiskLevel, ConversationState } from "@/types";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [accessCode, setAccessCode] = useState<string | null>(null);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [riskResources, setRiskResources] = useState<Record<string, string> | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    // Get access code from session storage
    const code = sessionStorage.getItem("patient_access_code");
    if (!code) {
      router.push("/patient");
      return;
    }
    setAccessCode(code);
  }, [router]);

  useEffect(() => {
    // Scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !accessCode || loading) return;

    const userMessage = input.trim();
    setInput("");
    setLoading(true);

    // Add user message to UI immediately
    const tempUserMsg: Message = {
      id: Date.now().toString(),
      role: "user" as any,
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await apiClient.sendMessage(
        accessCode,
        userMessage,
        sessionId || undefined
      );

      // Update session ID if this is first message
      if (!sessionId) {
        setSessionId(response.session_id);
      }

      // Add assistant response
      setMessages((prev) => [...prev, response.message]);

      // Handle risk detection
      if (response.risk_detected) {
        if (response.risk_level === RiskLevel.HIGH) {
          setSessionEnded(true);
          setRiskResources(response.resources || null);
        }
      }

      // Handle session end
      if (response.should_end_session) {
        setSessionEnded(true);
      }
    } catch (error: any) {
      console.error("Error sending message:", error);

      // Add error message
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: "assistant" as any,
        content: `Sorry, there was an error: ${error.message || "Unknown error"}. Please try again.`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleEndSession = async () => {
    if (sessionId && accessCode) {
      try {
        await apiClient.endSession(sessionId, accessCode);
      } catch (error) {
        console.error("Error ending session:", error);
      }
    }
    router.push("/patient");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!accessCode) {
    return <div>Loading...</div>;
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            CBT Skills Practice
          </h1>
          <p className="text-sm text-gray-500">
            {sessionId ? `Session active` : "Starting new session..."}
          </p>
        </div>
        <button
          onClick={handleEndSession}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
        >
          End Session
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-6 py-4 ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-900 shadow-sm border border-gray-200"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
                {msg.risk_level && msg.risk_level !== RiskLevel.NONE && (
                  <div className="mt-2 text-xs opacity-75">
                    Risk detected: {msg.risk_level}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white text-gray-900 shadow-sm border border-gray-200 rounded-2xl px-6 py-4">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200"></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Risk Resources Alert */}
      {riskResources && (
        <div className="bg-red-50 border-t border-red-200 px-6 py-4">
          <div className="max-w-3xl mx-auto">
            <h3 className="font-semibold text-red-900 mb-2">
              Crisis Resources
            </h3>
            <div className="text-sm text-red-800 space-y-1">
              {Object.entries(riskResources).map(([key, value]) => (
                <div key={key}>
                  <strong>{key}:</strong> {value}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="bg-white border-t border-gray-200 px-6 py-4">
        <div className="max-w-3xl mx-auto">
          {sessionEnded ? (
            <div className="text-center py-4">
              <p className="text-gray-600 mb-4">
                This session has ended. Please start a new session or contact
                your therapist.
              </p>
              <button
                onClick={() => router.push("/patient")}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Back to Portal
              </button>
            </div>
          ) : (
            <div className="flex items-end space-x-4">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message..."
                rows={2}
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
