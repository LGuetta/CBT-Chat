"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { TherapistDashboard, PatientOverview, RiskEvent } from "@/types";
import { format } from "date-fns";

export default function TherapistDashboardPage() {
  const [dashboard, setDashboard] = useState<TherapistDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [therapistEmail, setTherapistEmail] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const email = sessionStorage.getItem("therapist_email");
    if (!email) {
      router.push("/therapist");
      return;
    }
    setTherapistEmail(email);
    loadDashboard(email);
  }, [router]);

  const loadDashboard = async (email: string) => {
    try {
      setLoading(true);
      const data = await apiClient.getTherapistDashboard(email);
      setDashboard(data);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  const handleReviewFlag = async (flagId: string) => {
    if (!therapistEmail) return;

    try {
      await apiClient.reviewRiskEvent(flagId, therapistEmail);
      // Reload dashboard
      loadDashboard(therapistEmail);
    } catch (err: any) {
      alert("Error reviewing flag: " + err.message);
    }
  };

  const handleViewTranscript = (sessionId: string) => {
    router.push(`/therapist/session/${sessionId}`);
  };

  const handleViewPatient = (patientId: string) => {
    router.push(`/therapist/patient/${patientId}`);
  };

  const handleExport = async (patientId: string, format: "json" | "csv") => {
    if (!therapistEmail) return;

    try {
      const blob =
        format === "json"
          ? await apiClient.exportPatientDataJSON(patientId, therapistEmail)
          : await apiClient.exportPatientDataCSV(patientId, therapistEmail);

      // Download file
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `patient_${patientId}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert("Export failed: " + err.message);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">⏳</div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">❌</div>
          <p className="text-red-600 mb-4">{error || "Failed to load dashboard"}</p>
          <button
            onClick={() => router.push("/therapist")}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Therapist Dashboard
            </h1>
            <p className="text-sm text-gray-600">
              Welcome, {dashboard.therapist_name}
            </p>
          </div>
          <button
            onClick={() => {
              sessionStorage.removeItem("therapist_email");
              router.push("/therapist");
            }}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Patients</p>
                <p className="text-3xl font-bold text-gray-900">
                  {dashboard.patients.length}
                </p>
              </div>
              <div className="text-4xl">👥</div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Unreviewed Flags</p>
                <p className="text-3xl font-bold text-red-600">
                  {dashboard.total_unreviewed_flags}
                </p>
              </div>
              <div className="text-4xl">🚩</div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Active Sessions</p>
                <p className="text-3xl font-bold text-green-600">
                  {dashboard.patients.reduce((sum, p) => sum + p.total_sessions, 0)}
                </p>
              </div>
              <div className="text-4xl">💬</div>
            </div>
          </div>
        </div>

        {/* Recent Flags */}
        {dashboard.recent_flags.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-red-200 mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <span className="text-2xl mr-2">🚨</span>
              Recent Risk Flags
            </h2>
            <div className="space-y-4">
              {dashboard.recent_flags.slice(0, 5).map((flag) => (
                <div
                  key={flag.id}
                  className="flex items-center justify-between p-4 bg-red-50 rounded-lg"
                >
                  <div className="flex-1">
                    <div className="flex items-center space-x-3">
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded ${
                          flag.risk_level === "high"
                            ? "bg-red-600 text-white"
                            : "bg-orange-500 text-white"
                        }`}
                      >
                        {flag.risk_level.toUpperCase()}
                      </span>
                      <span className="font-medium text-gray-900">
                        Patient ID: {flag.patient_id.slice(0, 8)}...
                      </span>
                      <span className="text-sm text-gray-600">
                        {format(new Date(flag.created_at), "MMM d, h:mm a")}
                      </span>
                    </div>
                    {flag.detected_keywords.length > 0 && (
                      <div className="mt-2 text-sm text-gray-700">
                        Keywords: {flag.detected_keywords.join(", ")}
                      </div>
                    )}
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => handleViewTranscript(flag.session_id)}
                      className="px-3 py-1 text-sm bg-white text-gray-700 rounded hover:bg-gray-100"
                    >
                      View
                    </button>
                    {!flag.therapist_reviewed && (
                      <button
                        onClick={() => handleReviewFlag(flag.id)}
                        className="px-3 py-1 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700"
                      >
                        Mark Reviewed
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Patients List */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Your Patients
            </h2>
          </div>
          <div className="divide-y divide-gray-200">
            {dashboard.patients.map((patient) => (
              <div key={patient.patient_id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3">
                      <h3 className="font-semibold text-gray-900">
                        {patient.preferred_name || "Anonymous"}
                      </h3>
                      <span className="text-sm text-gray-500">
                        ({patient.access_code})
                      </span>
                      {patient.unreviewed_risk_events > 0 && (
                        <span className="px-2 py-1 text-xs font-semibold bg-red-100 text-red-800 rounded">
                          {patient.unreviewed_risk_events} unreviewed flags
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center space-x-4 text-sm text-gray-600">
                      <span>Sessions: {patient.total_sessions}</span>
                      <span>Flagged: {patient.flagged_sessions}</span>
                      {patient.last_session_date && (
                        <span>
                          Last session:{" "}
                          {format(new Date(patient.last_session_date), "MMM d, yyyy")}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => handleViewPatient(patient.patient_id)}
                      className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                    >
                      View Details
                    </button>
                    <button
                      onClick={() => handleExport(patient.patient_id, "json")}
                      className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                    >
                      Export
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
