"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { apiClient } from "@/lib/api";
import { SessionTranscript, RiskEvent } from "@/types";
import { format } from "date-fns";

export default function SessionTranscriptPage() {
  const [transcript, setTranscript] = useState<SessionTranscript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [therapistEmail, setTherapistEmail] = useState<string | null>(null);
  const [reviewingEventId, setReviewingEventId] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState<string>("");
  const [reviewingLoading, setReviewingLoading] = useState(false);
  const router = useRouter();
  const params = useParams();
  const sessionId = params?.sessionId as string;

  useEffect(() => {
    const email = sessionStorage.getItem("therapist_email");
    if (!email) {
      router.push("/therapist");
      return;
    }
    setTherapistEmail(email);

    if (sessionId) {
      loadTranscript(sessionId, email);
    }
  }, [sessionId, router]);

  const loadTranscript = async (id: string, email: string) => {
    try {
      setLoading(true);
      const data = await apiClient.getSessionTranscript(id, email);
      setTranscript(data);
    } catch (err: any) {
      setError(err.message || "Failed to load transcript");
    } finally {
      setLoading(false);
    }
  };

  const handleReviewEvent = async (eventId: string) => {
    if (!therapistEmail) return;
    
    setReviewingLoading(true);
    try {
      await apiClient.reviewRiskEvent(eventId, therapistEmail, reviewNotes || undefined);
      
      // Update local state to mark as reviewed
      if (transcript) {
        setTranscript({
          ...transcript,
          risk_events: transcript.risk_events.map((event) =>
            event.id === eventId
              ? { ...event, therapist_reviewed: true }
              : event
          ),
        });
      }
      
      // Reset review state
      setReviewingEventId(null);
      setReviewNotes("");
    } catch (err: any) {
      alert("Failed to mark as reviewed: " + (err.message || "Unknown error"));
    } finally {
      setReviewingLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">⏳</div>
          <p className="text-gray-600">Loading transcript...</p>
        </div>
      </div>
    );
  }

  if (error || !transcript) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">❌</div>
          <p className="text-red-600 mb-4">{error || "Failed to load transcript"}</p>
          <button
            onClick={() => router.push("/therapist/dashboard")}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const session = transcript.session;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto">
          <button
            onClick={() => router.push("/therapist/dashboard")}
            className="text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            ← Back to Dashboard
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Session Transcript</h1>
          <div className="mt-2 flex items-center space-x-4 text-sm text-gray-600">
            <span>Session ID: {session.id.slice(0, 8)}...</span>
            <span>
              Started: {format(new Date(session.started_at), "MMM d, yyyy h:mm a")}
            </span>
            <span className="capitalize">Status: {session.status}</span>
            {session.risk_flagged && (
              <span className="px-2 py-1 bg-red-100 text-red-800 rounded font-semibold">
                🚩 Flagged
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {/* AI Summary */}
        {transcript.ai_summary && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-6 mb-8">
            <h2 className="text-lg font-semibold text-indigo-900 mb-4 flex items-center gap-2">
              <span>🤖</span>
              Session Summary
            </h2>
            <div className="text-indigo-900 max-w-none space-y-1">
              {transcript.ai_summary.split('\n').map((line, idx) => {
                if (!line.trim()) return null;
                
                // Check if it's a section header (starts with **)
                const isHeader = line.startsWith('**') && !line.startsWith('   ');
                
                return (
                  <div 
                    key={idx} 
                    className={`${isHeader ? 'mt-3 first:mt-0' : ''} ${line.startsWith('   ') ? 'ml-4' : ''}`}
                  >
                    <span 
                      dangerouslySetInnerHTML={{ 
                        __html: line
                          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                          .replace(/\"(.*?)\"/g, '<em class="text-indigo-700">"$1"</em>')
                      }} 
                    />
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Risk Events */}
        {transcript.risk_events.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-8">
            <h2 className="text-lg font-semibold text-red-900 mb-4">
              ⚠️ Risk Events ({transcript.risk_events.length})
            </h2>
            <div className="space-y-4">
              {transcript.risk_events.map((event) => (
                <div key={event.id} className="bg-white rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`px-2 py-1 text-xs font-semibold rounded ${
                        event.risk_level === "high"
                          ? "bg-red-600 text-white"
                          : "bg-orange-500 text-white"
                      }`}
                    >
                      {event.risk_level.toUpperCase()}
                    </span>
                    <span className="text-sm text-gray-500">
                      {format(new Date(event.created_at), "h:mm a")}
                    </span>
                  </div>
                  {event.detected_keywords.length > 0 && (
                    <p className="text-sm text-gray-700">
                      <strong>Keywords:</strong> {event.detected_keywords.join(", ")}
                    </p>
                  )}
                  {event.risk_type && (
                    <p className="text-sm text-gray-700 mt-1">
                      <strong>Type:</strong> {event.risk_type}
                    </p>
                  )}
                  
                  {/* Review Section */}
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    {event.therapist_reviewed ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs px-2 py-1 rounded bg-green-100 text-green-800">
                          ✓ Reviewed
                        </span>
                      </div>
                    ) : reviewingEventId === event.id ? (
                      <div className="space-y-3">
                        <textarea
                          value={reviewNotes}
                          onChange={(e) => setReviewNotes(e.target.value)}
                          placeholder="Add clinical notes about this risk event (optional)..."
                          className="w-full p-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                          rows={3}
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleReviewEvent(event.id)}
                            disabled={reviewingLoading}
                            className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                          >
                            {reviewingLoading ? "Saving..." : "✓ Mark as Reviewed"}
                          </button>
                          <button
                            onClick={() => {
                              setReviewingEventId(null);
                              setReviewNotes("");
                            }}
                            className="px-3 py-1.5 text-sm bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setReviewingEventId(event.id)}
                        className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                      >
                        📝 Review This Event
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Session Info */}
        {session.session_goal && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-8">
            <h3 className="font-semibold text-blue-900 mb-2">Session Goal</h3>
            <p className="text-blue-800">{session.session_goal}</p>
          </div>
        )}

        {/* Skills Completed */}
        {transcript.skill_completions.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Skills Practiced ({transcript.skill_completions.length})
            </h2>
            <div className="space-y-3">
              {transcript.skill_completions.map((skill) => (
                <div
                  key={skill.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <span className="font-medium text-gray-900 capitalize">
                      {skill.skill_type.replace("_", " ")}
                    </span>
                    {skill.mood_before !== undefined && skill.mood_after !== undefined && (
                      <span className="ml-3 text-sm text-gray-600">
                        Mood: {skill.mood_before} → {skill.mood_after}
                      </span>
                    )}
                  </div>
                  <span className="text-sm text-gray-500">
                    {format(new Date(skill.completed_at), "h:mm a")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Full Transcript */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">
            Full Conversation
          </h2>
          <div className="space-y-4">
            {transcript.messages.map((msg, index) => (
              <div
                key={msg.id}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-xl px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-blue-100 text-gray-900"
                      : "bg-gray-100 text-gray-900"
                  }`}
                >
                  <div className="flex items-center space-x-2 mb-1">
                    <span className="text-xs font-semibold uppercase text-gray-600">
                      {msg.role}
                    </span>
                    <span className="text-xs text-gray-500">
                      {format(new Date(msg.created_at), "h:mm a")}
                    </span>
                  </div>
                  <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
                  {msg.risk_level && msg.risk_level !== "none" && (
                    <div className="mt-2 text-xs text-red-600 font-semibold">
                      ⚠️ Risk: {msg.risk_level}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
