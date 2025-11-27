"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { Message, RiskLevel, DistressLevel } from "@/types";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [accessCode, setAccessCode] = useState<string | null>(null);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [riskResources, setRiskResources] = useState<Record<string, string> | null>(null);
  const [currentDistress, setCurrentDistress] = useState<DistressLevel>(DistressLevel.NONE);
  const [currentRisk, setCurrentRisk] = useState<RiskLevel>(RiskLevel.NONE);
  const [riskBanner, setRiskBanner] = useState<{
    level: RiskLevel;
    reasoning?: string;
    triggers?: string[];
    resources?: Record<string, string> | null;
  } | null>(null);

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
        return { text: "Crisis Support", icon: "🚨" };
      case DistressLevel.SEVERE:
        return { text: "High Distress", icon: "⚠️" };
      case DistressLevel.MODERATE:
        return { text: "Moderate Distress", icon: "⚡" };
      case DistressLevel.MILD:
        return { text: "Mild Distress", icon: "💭" };
      default:
        return null;
    }
  };

  const getRiskChip = (level?: RiskLevel) => {
    switch (level) {
      case RiskLevel.HIGH:
        return { text: "High Risk", className: "bg-red-100 text-red-700", icon: "🚨" };
      case RiskLevel.MEDIUM:
        return { text: "Monitor Closely", className: "bg-orange-100 text-orange-700", icon: "⚠️" };
      case RiskLevel.LOW:
        return { text: "Low Risk", className: "bg-yellow-100 text-yellow-700", icon: "🟡" };
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
        sessionId || undefined
      );

      // Update session ID if this is first message
      if (!sessionId) {
        setSessionId(response.session_id);
      }

      // Mark message with metadata
      const enhancedMessage: Message = {
        ...response.message,
        distress_level: response.distress_level,
        is_grounding_exercise: response.grounding_offered,
        is_disclaimer: response.disclaimer_shown,
        risk_level: response.risk_level,
        risk_reasoning: response.risk_reasoning,
        risk_triggers: response.risk_triggers,
      };

      // Update user message metadata + append assistant response
      setMessages((prev) => {
        const updated = [...prev];
        if (updated.length > 0) {
          const lastIndex = updated.length - 1;
          updated[lastIndex] = {
            ...updated[lastIndex],
            risk_level: response.risk_level,
            risk_reasoning: response.risk_reasoning,
            distress_level: response.distress_level ?? updated[lastIndex].distress_level,
          };
        }
        return [...updated, enhancedMessage];
      });

      // Update current distress level
      if (response.distress_level) {
        setCurrentDistress(response.distress_level);
      }

      // Update current risk indicator
      setCurrentRisk(response.risk_level);

      // Handle risk detection banner/resources
      if (response.risk_detected) {
        setRiskBanner({
          level: response.risk_level,
          reasoning: response.risk_reasoning,
          triggers: response.risk_triggers || [],
          resources: response.resources || null,
        });
        setRiskResources(response.resources || null);

        if (response.risk_level === RiskLevel.HIGH) {
          setSessionEnded(true);
        }
      } else {
        setRiskBanner(null);
        setRiskResources(null);
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
            {currentRisk !== RiskLevel.NONE && (
              <span
                className={`text-xs px-2 py-1 rounded-full ${
                  getRiskChip(currentRisk)?.className
                }`}
              >
                {getRiskChip(currentRisk)?.icon} {getRiskChip(currentRisk)?.text}
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

      {/* Risk Banner */}
      {riskBanner && (
        <div className="bg-white border-b border-t border-red-200 px-6 py-3">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center gap-2 text-red-800 font-semibold">
              <span>{getRiskChip(riskBanner.level)?.icon}</span>
              <span>{getRiskChip(riskBanner.level)?.text}</span>
            </div>
            {riskBanner.reasoning && (
              <p className="text-sm text-red-700 mt-1">{riskBanner.reasoning}</p>
            )}
            {riskBanner.triggers && riskBanner.triggers.length > 0 && (
              <p className="text-xs text-red-600 mt-1">
                Triggers: {riskBanner.triggers.join(", ")}
              </p>
            )}
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

                {/* Risk/Distress indicators */}
                {(msg.risk_level || msg.distress_level) && (
                  <div className="mt-3 pt-2 border-t border-gray-200 flex gap-3 text-xs">
                    {msg.risk_level && msg.risk_level !== RiskLevel.NONE && (
                      <div className="flex flex-col">
                        <span
                          className={`px-2 py-1 rounded ${
                            msg.risk_level === RiskLevel.HIGH
                              ? "bg-red-100 text-red-700"
                              : msg.risk_level === RiskLevel.MEDIUM
                              ? "bg-orange-100 text-orange-700"
                              : "bg-yellow-100 text-yellow-700"
                          }`}
                        >
                          Risk: {msg.risk_level}
                        </span>
                        {msg.risk_reasoning && (
                          <span className="mt-1 text-[11px] text-gray-600 max-w-xs">
                            {msg.risk_reasoning}
                          </span>
                        )}
                      </div>
                    )}
                    {msg.distress_level && msg.distress_level !== DistressLevel.NONE && (
                      <span className="px-2 py-1 rounded bg-gray-100 text-gray-600">
                        {getDistressLabel(msg.distress_level)?.icon} {msg.distress_level}
                      </span>
                    )}
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
            <h3 className="font-semibold text-red-900 mb-2 flex items-center gap-2">
              <span className="text-xl">🚨</span>
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
          <p className="text-xs text-gray-500 mb-3">
            You are interacting with a conversational AI agent. Responses are automated,
            informational, and do not replace professional clinical care.
          </p>
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
