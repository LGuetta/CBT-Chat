"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const COUNTRY_OPTIONS = [
  { code: "us", name: "United States", flag: "🇺🇸" },
  { code: "uk", name: "United Kingdom", flag: "🇬🇧" },
  { code: "it", name: "Italy", flag: "🇮🇹" },
  { code: "de", name: "Germany", flag: "🇩🇪" },
  { code: "fr", name: "France", flag: "🇫🇷" },
  { code: "es", name: "Spain", flag: "🇪🇸" },
  { code: "ch", name: "Switzerland", flag: "🇨🇭" },
  { code: "at", name: "Austria", flag: "🇦🇹" },
  { code: "nl", name: "Netherlands", flag: "🇳🇱" },
  { code: "be", name: "Belgium", flag: "🇧🇪" },
  { code: "other", name: "Other", flag: "🌍" },
];

export default function PatientPortal() {
  const [accessCode, setAccessCode] = useState("");
  const [country, setCountry] = useState("us");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!accessCode.trim()) {
      setError("Please enter your access code");
      return;
    }

    // Store access code and country, then navigate to chat
    sessionStorage.setItem("patient_access_code", accessCode.trim());
    sessionStorage.setItem("patient_country", country);
    router.push("/patient/chat");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Welcome Back
          </h1>
          <p className="text-gray-600">
            Enter your access code to start a session
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label
              htmlFor="accessCode"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Access Code
            </label>
            <input
              type="text"
              id="accessCode"
              value={accessCode}
              onChange={(e) => {
                setAccessCode(e.target.value);
                setError("");
              }}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Enter your code (e.g., PATIENT001)"
            />
            {error && (
              <p className="mt-2 text-sm text-red-600">{error}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="country"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Your Country
            </label>
            <select
              id="country"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
            >
              {COUNTRY_OPTIONS.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.flag} {c.name}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              Used for emergency resources in your region
            </p>
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors"
          >
            Start Session
          </button>
        </form>

        <div className="mt-8 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm text-gray-700">
            <strong>New here?</strong> Your therapist will provide you with an
            access code to get started.
          </p>
        </div>

        <div className="mt-4 text-center">
          <a
            href="/"
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            ← Back to home
          </a>
        </div>
      </div>
    </div>
  );
}
