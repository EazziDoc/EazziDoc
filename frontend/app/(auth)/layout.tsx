export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary-600 text-white font-bold text-xl mb-3">
            E
          </div>
          <h1 className="text-2xl font-bold text-gray-900">EazziDoc</h1>
          <p className="text-sm text-gray-500 mt-1">AI-powered medical diagnostics</p>
        </div>
        {children}
      </div>
    </div>
  );
}
