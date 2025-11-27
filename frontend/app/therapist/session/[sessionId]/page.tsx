"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { apiClient } from "@/lib/api";
import { SessionTranscript } from "@/types";
import { format } from "date-fns";

export default function SessionTranscriptPage() {
  const [transcript, setTranscript] = useState<SessionTranscript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const params = useParams();
  const sessionId = params?.sessionId as string;

  useEffect(() => {
    const email = sessionStorage.getItem("therapist_email");
    if (!email) {
      router.push("/therapist");
      return;
    }

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
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-900">AI Session Summary</h2>
            {!session.ai_summary && (
              <span className="text-xs text-gray-500">Generated at session end</span>
            )}
          </div>
          {session.ai_summary ? (
            <p className="text-gray-800 leading-relaxed">{session.ai_summary}</p>
          ) : (
            <p className="text-gray-500 text-sm">
              No AI summary available for this session yet.
            </p>
          )}
        </div>

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
                  <span
                    className={`inline-block mt-2 text-xs px-2 py-1 rounded ${
                      event.therapist_reviewed
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {event.therapist_reviewed ? "✓ Reviewed" : "Pending Review"}
                  </span>
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
