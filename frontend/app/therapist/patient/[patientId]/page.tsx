"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import { apiClient } from "@/lib/api";
import {
  PatientDetails,
  TherapistBrief,
  PreferredTechniques,
  RiskLevel,
} from "@/types";

const defaultTechniques: PreferredTechniques = {
  cognitive_restructuring: true,
  behavioral_activation: true,
  exposure: false,
  distress_tolerance: true,
  schema_work: false,
};

const defaultBrief: TherapistBrief = {
  therapy_stage: "early",
  presenting_problems: [],
  treatment_goals: [],
  preferred_techniques: defaultTechniques,
  sensitivities: {
    trauma_history: "",
    pacing: "moderate",
    topics_to_avoid: [],
  },
  therapist_language: {
    metaphors: [],
    coping_statements: [],
    preferred_terms: {},
  },
  contraindications: [],
};

const stageOptions = [
  { value: "early", label: "Early - Rapport & Psychoeducation" },
  { value: "middle", label: "Middle - Active CBT Work" },
  { value: "late", label: "Late - Consolidation" },
];

const listFromTextarea = (value: string) =>
  value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const textareaFromList = (items?: string[]) => (items && items.length ? items.join("\n") : "");

const hydrateBrief = (incoming?: TherapistBrief | null): TherapistBrief => ({
  ...defaultBrief,
  ...incoming,
  preferred_techniques: {
    ...defaultTechniques,
    ...(incoming?.preferred_techniques || {}),
  },
  sensitivities: {
    ...defaultBrief.sensitivities,
    ...(incoming?.sensitivities || {}),
    topics_to_avoid: incoming?.sensitivities?.topics_to_avoid || [],
  },
  therapist_language: {
    ...defaultBrief.therapist_language,
    ...(incoming?.therapist_language || {}),
    metaphors: incoming?.therapist_language?.metaphors || [],
    coping_statements: incoming?.therapist_language?.coping_statements || [],
    preferred_terms: incoming?.therapist_language?.preferred_terms || {},
  },
  presenting_problems: incoming?.presenting_problems || [],
  treatment_goals: incoming?.treatment_goals || [],
  contraindications: incoming?.contraindications || [],
});

export default function PatientDetailPage() {
  const params = useParams();
  const patientId = params?.patientId as string;
  const router = useRouter();

  const [therapistEmail, setTherapistEmail] = useState<string | null>(null);
  const [details, setDetails] = useState<PatientDetails | null>(null);
  const [briefForm, setBriefForm] = useState<TherapistBrief>(defaultBrief);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    const email = sessionStorage.getItem("therapist_email");
    if (!email) {
      router.push("/therapist");
      return;
    }
    setTherapistEmail(email);
  }, [router]);

  useEffect(() => {
    if (!therapistEmail || !patientId) return;
    const fetchDetails = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient.getPatientDetails(patientId, therapistEmail);
        setDetails(data);
        setBriefForm(hydrateBrief(data.patient.therapist_brief));
      } catch (err: any) {
        setError(err.message || "Failed to load patient details");
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [therapistEmail, patientId]);

  const handleTechniqueToggle = (key: keyof PreferredTechniques) => {
    setBriefForm((prev) => ({
      ...prev,
      preferred_techniques: {
        ...prev.preferred_techniques,
        [key]: !prev.preferred_techniques?.[key],
      },
    }));
  };

  const handleBriefSave = async () => {
    if (!therapistEmail) return;
    setSaving(true);
    setSuccessMessage(null);
    setError(null);
    try {
      await apiClient.updatePatientBrief(patientId, therapistEmail, briefForm);
      setSuccessMessage("Therapist brief updated");
    } catch (err: any) {
      setError(err.message || "Failed to update brief");
    } finally {
      setSaving(false);
    }
  };

  const riskBadge = (level: RiskLevel) => {
    switch (level) {
      case RiskLevel.HIGH:
        return "bg-red-100 text-red-700";
      case RiskLevel.MEDIUM:
        return "bg-orange-100 text-orange-700";
      case RiskLevel.LOW:
        return "bg-yellow-100 text-yellow-700";
      default:
        return "bg-gray-100 text-gray-600";
    }
  };

  if (!therapistEmail || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-2">⌛</div>
          <p className="text-gray-600">Loading patient details...</p>
        </div>
      </div>
    );
  }

  if (error || !details) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="text-4xl mb-2">⚠️</div>
          <p className="text-red-600">{error || "Unable to load patient"}</p>
          <button
            onClick={() => router.push("/therapist/dashboard")}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    );
  }

  const patient = details.patient;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="border-b bg-white px-6 py-4 flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">Patient Profile</p>
          <h1 className="text-2xl font-semibold text-gray-900">
            {patient.preferred_name || "Unnamed"} ({patient.access_code})
          </h1>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => router.push("/therapist/dashboard")}
            className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        {successMessage && (
          <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-2 rounded">
            {successMessage}
          </div>
        )}

        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Therapist Brief
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Case Formulation
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  rows={4}
                  value={briefForm.case_formulation || ""}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      case_formulation: e.target.value,
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Therapy Stage
                </label>
                <select
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  value={briefForm.therapy_stage || "early"}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      therapy_stage: e.target.value,
                    }))
                  }
                >
                  {stageOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Treatment Goals (one per line)
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                  value={textareaFromList(briefForm.treatment_goals)}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      treatment_goals: listFromTextarea(e.target.value),
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Presenting Problems (one per line)
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                  value={textareaFromList(briefForm.presenting_problems)}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      presenting_problems: listFromTextarea(e.target.value),
                    }))
                  }
                />
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">
                  Preferred Techniques
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {Object.keys(defaultTechniques).map((technique) => (
                    <label
                      key={technique}
                      className="flex items-center space-x-2 text-sm text-gray-700"
                    >
                      <input
                        type="checkbox"
                        checked={!!briefForm.preferred_techniques?.[technique as keyof PreferredTechniques]}
                        onChange={() =>
                          handleTechniqueToggle(technique as keyof PreferredTechniques)
                        }
                      />
                      <span className="capitalize">
                        {technique.replace("_", " ")}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Sensitivities / Topics to Avoid
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                  value={textareaFromList(briefForm.sensitivities?.topics_to_avoid)}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      sensitivities: {
                        ...prev.sensitivities,
                        topics_to_avoid: listFromTextarea(e.target.value),
                      },
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Therapist Language / Metaphors
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                  value={textareaFromList(briefForm.therapist_language?.metaphors)}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      therapist_language: {
                        ...prev.therapist_language,
                        metaphors: listFromTextarea(e.target.value),
                      },
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Coping Statements (one per line)
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                  value={textareaFromList(briefForm.therapist_language?.coping_statements)}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      therapist_language: {
                        ...prev.therapist_language,
                        coping_statements: listFromTextarea(e.target.value),
                      },
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Contraindications (one per line)
                </label>
                <textarea
                  className="mt-1 w-full rounded-lg border border-gray-300 p-3 focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                  value={textareaFromList(briefForm.contraindications)}
                  onChange={(e) =>
                    setBriefForm((prev) => ({
                      ...prev,
                      contraindications: listFromTextarea(e.target.value),
                    }))
                  }
                />
              </div>
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <button
              onClick={handleBriefSave}
              disabled={saving}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Therapist Brief"}
            </button>
          </div>
        </section>

        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Sessions</h2>
            <p className="text-sm text-gray-500">
              Showing last {details.recent_sessions.length} sessions
            </p>
          </div>
          {details.recent_sessions.length === 0 ? (
            <p className="text-gray-500">No sessions recorded yet.</p>
          ) : (
            <div className="space-y-3">
              {details.recent_sessions.map((session) => (
                <div
                  key={session.id}
                  className="border border-gray-200 rounded-lg p-4 flex items-center justify-between"
                >
                  <div>
                    <p className="font-semibold text-gray-900">
                      {new Date(session.started_at).toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-500">
                      State: {session.current_state} · Messages: {session.total_messages}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${riskBadge(session.risk_level)}`}
                    >
                      Risk: {session.risk_level}
                    </span>
                    <button
                      onClick={() =>
                        router.push(`/therapist/session/${session.id}`)
                      }
                      className="text-sm text-indigo-600 hover:underline"
                    >
                      View transcript
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Risk Events</h2>
            <p className="text-sm text-gray-500">
              {details.recent_risk_events.length} flagged interactions
            </p>
          </div>
          {details.recent_risk_events.length === 0 ? (
            <p className="text-gray-500">No risk events recorded.</p>
          ) : (
            <div className="space-y-3">
              {details.recent_risk_events.map((event) => (
                <div
                  key={event.id}
                  className="border border-gray-200 rounded-lg p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
                >
                  <div>
                    <p className="font-semibold text-gray-900">
                      {new Date(event.created_at).toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-500">
                      Keywords: {event.detected_keywords.join(", ")}
                    </p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full ${riskBadge(event.risk_level)}`}>
                    {event.risk_level.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

