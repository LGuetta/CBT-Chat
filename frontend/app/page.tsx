import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-2xl mx-auto p-8 text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-4">
          CBT Chat Assistant
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          Practice CBT skills between therapy sessions with AI-guided support
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-12">
          <Link
            href="/patient"
            className="group p-8 bg-white rounded-2xl shadow-lg hover:shadow-xl transition-all border-2 border-transparent hover:border-blue-500"
          >
            <div className="text-4xl mb-4">💬</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              Patient Portal
            </h2>
            <p className="text-gray-600">
              Start a CBT skills practice session
            </p>
          </Link>

          <Link
            href="/therapist"
            className="group p-8 bg-white rounded-2xl shadow-lg hover:shadow-xl transition-all border-2 border-transparent hover:border-indigo-500"
          >
            <div className="text-4xl mb-4">🩺</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              Therapist Dashboard
            </h2>
            <p className="text-gray-600">
              Monitor patients and review sessions
            </p>
          </Link>
        </div>

        <div className="mt-12 p-6 bg-white rounded-xl shadow-md">
          <h3 className="font-semibold text-gray-900 mb-2">
            What you can practice:
          </h3>
          <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
            <div>✓ Thought Records</div>
            <div>✓ Behavioral Activation</div>
            <div>✓ Exposure Practice</div>
            <div>✓ Coping Skills</div>
          </div>
        </div>

        <p className="mt-8 text-sm text-gray-500">
          This tool is NOT a replacement for therapy or crisis services.
        </p>
      </div>
    </main>
  );
}
