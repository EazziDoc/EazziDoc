import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-primary-600 text-white flex items-center justify-center font-bold text-sm">
            E
          </div>
          <span className="font-semibold text-gray-900 text-lg">EazziDoc</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/login" className="text-sm text-gray-600 hover:text-gray-900">
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-8 py-24 text-center">
        <span className="inline-block rounded-full bg-primary-50 px-4 py-1.5 text-sm font-medium text-primary-700 mb-6">
          AI-Powered Medical Imaging
        </span>
        <h1 className="text-5xl font-bold text-gray-900 mb-6 leading-tight">
          Expert diagnostics, <br />
          <span className="text-primary-600">accessible to everyone</span>
        </h1>
        <p className="text-xl text-gray-500 mb-10 max-w-2xl mx-auto">
          Upload your medical images and receive AI-generated diagnostic reports in minutes.
          Connect with doctors for expert review — wherever you are in Africa.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link
            href="/register"
            className="rounded-lg bg-primary-600 px-6 py-3 text-base font-medium text-white hover:bg-primary-700"
          >
            Start diagnosis →
          </Link>
          <Link
            href="/register?role=doctor"
            className="rounded-lg border border-gray-300 px-6 py-3 text-base font-medium text-gray-700 hover:bg-gray-50"
          >
            Join as a doctor
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="bg-gray-50 py-20">
        <div className="mx-auto max-w-5xl px-8">
          <h2 className="text-center text-3xl font-bold text-gray-900 mb-12">
            How it works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                step: "01",
                title: "Upload your images",
                desc: "Upload up to 5 medical images per session — chest X-rays, eye scans, skin photos, and more.",
              },
              {
                step: "02",
                title: "AI analysis",
                desc: "Our AI detects the image modality, analyses findings, and generates a structured diagnostic report.",
              },
              {
                step: "03",
                title: "Doctor review",
                desc: "A verified doctor reviews the AI report, adds clinical notes, and confirms or updates the diagnosis.",
              },
            ].map((f) => (
              <div key={f.step} className="rounded-xl bg-white p-6 border border-gray-200">
                <span className="text-4xl font-bold text-primary-200">{f.step}</span>
                <h3 className="mt-4 text-lg font-semibold text-gray-900">{f.title}</h3>
                <p className="mt-2 text-sm text-gray-500">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Supported modalities */}
      <section className="py-20">
        <div className="mx-auto max-w-4xl px-8 text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">Supported imaging types</h2>
          <p className="text-gray-500 mb-10">
            Our AI is trained to analyse the most common medical imaging modalities.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {["Chest X-Ray", "Fundus (Eye)", "Skin Lesions", "Brain MRI", "Mammography"].map(
              (m) => (
                <span
                  key={m}
                  className="rounded-full border border-primary-200 bg-primary-50 px-4 py-2 text-sm font-medium text-primary-700"
                >
                  {m}
                </span>
              ),
            )}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} EazziDoc · Built for Africa
      </footer>
    </main>
  );
}
