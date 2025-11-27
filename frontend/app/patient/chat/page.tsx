"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { Message, RiskLevel, DistressLevel } from "@/types";

// RiskLevel is still imported for type checking API responses

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [accessCode, setAccessCode] = useState<string | null>(null);
  const [country, setCountry] = useState<string>("us");
  const [sessionEnded, setSessionEnded] = useState(false);
  const [crisisResources, setCrisisResources] = useState<Record<string, string> | null>(null);
  const [currentDistress, setCurrentDistress] = useState<DistressLevel>(DistressLevel.NONE);
  const [showSupportBanner, setShowSupportBanner] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    // Get access code and country from session storage
    const code = sessionStorage.getItem("patient_access_code");
    const storedCountry = sessionStorage.getItem("patient_country");
    if (!code) {
      router.push("/patient");
      return;
    }
    setAccessCode(code);
    if (storedCountry) {
      setCountry(storedCountry);
    }
  }, [router]);

  useEffect(() => {
    // Scroll to bottom when messages change
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const getDistressColor = (level?: DistressLevel) => {
    switch (level) {
      case DistressLevel.CRISIS:
        return "bg-red-100 border-red-300";
      case DistressLevel.SEVERE:
        return "bg-orange-100 border-orange-300";
      case DistressLevel.MODERATE:
        return "bg-yellow-100 border-yellow-300";
      case DistressLevel.MILD:
        return "bg-blue-50 border-blue-200";
      default:
        return "bg-white border-gray-200";
    }
  };

  const getDistressLabel = (level?: DistressLevel) => {
    switch (level) {
      case DistressLevel.CRISIS:
        return { text: "We're here to help", icon: "💙" };
      case DistressLevel.SEVERE:
        return { text: "Take your time", icon: "🤗" };
      case DistressLevel.MODERATE:
        return { text: "Working through it", icon: "💪" };
      case DistressLevel.MILD:
        return { text: "Exploring", icon: "💭" };
      default:
        return null;
    }
  };

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
        sessionId || undefined,
        country // Pass country for localized resources
      );

      // Update session ID if this is first message
      if (!sessionId) {
        setSessionId(response.session_id);
      }

      // Mark message with metadata (no risk info for patient)
      const enhancedMessage: Message = {
        ...response.message,
        distress_level: response.distress_level,
        is_grounding_exercise: response.grounding_offered,
        is_disclaimer: response.disclaimer_shown,
      };

      // Update user message metadata + append assistant response
      setMessages((prev) => {
        const updated = [...prev];
        if (updated.length > 0) {
          const lastIndex = updated.length - 1;
          updated[lastIndex] = {
            ...updated[lastIndex],
            distress_level: response.distress_level ?? updated[lastIndex].distress_level,
          };
        }
        return [...updated, enhancedMessage];
      });

      // Update current distress level
      if (response.distress_level) {
        setCurrentDistress(response.distress_level);
      }

      // Handle crisis resources (show support without alarming the patient)
      if (response.risk_detected && response.resources) {
        setCrisisResources(response.resources);
        setShowSupportBanner(true);

        if (response.risk_level === RiskLevel.HIGH) {
          setSessionEnded(true);
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
          <div className="flex flex-wrap items-center gap-3 mt-1">
            <p className="text-sm text-gray-500">
              {sessionId ? `Session active` : "Starting new session..."}
            </p>
            {currentDistress !== DistressLevel.NONE && (
              <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700">
                {getDistressLabel(currentDistress)?.icon} {getDistressLabel(currentDistress)?.text}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={handleEndSession}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
        >
          End Session
        </button>
      </header>

      {/* Support Resources Banner - shown when needed, without alarming language */}
      {showSupportBanner && crisisResources && (
        <div className="bg-blue-50 border-b border-blue-200 px-6 py-3">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-2 text-blue-800 font-medium">
              <span>💙</span>
              <span>Support resources are available</span>
            </div>
            <p className="text-sm text-blue-700 mt-1">
              If you'd like to talk to someone, these resources are here for you.
            </p>
          </div>
        </div>
      )}

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
                    : msg.is_grounding_exercise
                    ? `${getDistressColor(msg.distress_level)} shadow-md border-2 border-l-4`
                    : msg.is_disclaimer
                    ? "bg-amber-50 text-gray-900 shadow-sm border-2 border-amber-200"
                    : "bg-white text-gray-900 shadow-sm border border-gray-200"
                }`}
              >
                {/* Special indicators */}
                {msg.role === "assistant" && msg.is_grounding_exercise && (
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-300">
                    <span className="text-2xl">🧘</span>
                    <span className="text-sm font-semibold text-gray-700">
                      Grounding Exercise
                    </span>
                  </div>
                )}

                {msg.role === "assistant" && msg.is_disclaimer && (
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-amber-300">
                    <span className="text-xl">ℹ️</span>
                    <span className="text-sm font-semibold text-amber-900">
                      Important Reminder
                    </span>
                  </div>
                )}

                {/* Message content */}
                <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

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

      {/* Support Resources - shown when needed */}
      {crisisResources && showSupportBanner && (
        <div className="bg-blue-50 border-t border-blue-200 px-6 py-4">
          <div className="max-w-3xl mx-auto">
            <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
              <span className="text-xl">💙</span>
              Support Resources
            </h3>
            <p className="text-sm text-blue-700 mb-3">
              If you'd like to talk to someone, these resources are available 24/7:
            </p>
            <div className="text-sm text-blue-800 space-y-1">
              {Object.entries(crisisResources).map(([key, value]) => (
                <div key={key}>
                  <strong>{key.replace(/_/g, " ")}:</strong> {value}
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
