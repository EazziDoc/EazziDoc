import Image from "next/image";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Image src="/logo.png" alt="EazziDoc" width={160} height={53} className="object-contain mx-auto mb-3" />
          <p className="text-sm text-gray-500 mt-1">AI-powered medical diagnostics</p>
        </div>
        {children}
      </div>
    </div>
  );
}
