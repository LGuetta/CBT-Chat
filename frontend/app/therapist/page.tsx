"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function TherapistLogin() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim() || !email.includes("@")) {
      setError("Please enter a valid email address");
      return;
    }

    // Store therapist email and navigate to dashboard
    sessionStorage.setItem("therapist_email", email.trim());
    router.push("/therapist/dashboard");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 to-purple-100 p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-8">
          <div className="text-5xl mb-4">🩺</div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Therapist Dashboard
          </h1>
          <p className="text-gray-600">
            Monitor your patients and review sessions
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Email Address
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setError("");
              }}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="therapist@example.com"
            />
            {error && (
              <p className="mt-2 text-sm text-red-600">{error}</p>
            )}
          </div>

          <button
            type="submit"
            className="w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
          >
            Access Dashboard
          </button>
        </form>

        <div className="mt-8 p-4 bg-indigo-50 rounded-lg">
          <p className="text-sm text-gray-700">
            <strong>For MVP:</strong> Use{" "}
            <code className="bg-gray-200 px-2 py-1 rounded">
              dr.smith@example.com
            </code>{" "}
            to access the test account.
          </p>
        </div>

        <div className="mt-4 text-center">
          <a href="/" className="text-sm text-gray-600 hover:text-gray-900">
            ← Back to home
          </a>
        </div>
      </div>
    </div>
  );
}
