"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { login, register, uploadCertifications } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input, PasswordInput } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

// ── Qualification catalogue ───────────────────────────────────────────────────

const QUALIFICATIONS = {
  "African Councils": [
    "MDCN (Medical and Dental Council of Nigeria)",
    "HPCSA (Health Professions Council of South Africa)",
    "Medical Council of Ghana (MCG)",
    "Kenya Medical Practitioners & Dentists Council (KMPDC)",
    "Medical Council of Uganda",
    "Tanzania Medical Council (TMC)",
    "Ethiopian Medical Council (EMC)",
    "West African College of Physicians (WACP)",
    "West African College of Surgeons (WACS)",
    "Fellow, West African College of Physicians (FWACP)",
    "Fellow, West African College of Surgeons (FWACS)",
    "College of Medicine of South Africa (CMSA)",
  ],
  "Undergraduate Degrees": [
    "MBBS",
    "MBChB",
    "MD (Doctor of Medicine)",
    "DO (Doctor of Osteopathic Medicine)",
    "BDS (Bachelor of Dental Surgery)",
    "MBBCh",
  ],
  "Postgraduate Degrees": [
    "PhD (Medical Sciences)",
    "MSc (Clinical Medicine)",
    "MPH (Master of Public Health)",
    "MMed (Master of Medicine)",
  ],
  "UK Royal College": [
    "MRCP (Member, Royal College of Physicians)",
    "MRCS (Member, Royal College of Surgeons)",
    "FRCP (Fellow, Royal College of Physicians)",
    "FRCS (Fellow, Royal College of Surgeons)",
    "MRCGP (Member, Royal College of General Practitioners)",
    "FRCR (Fellow, Royal College of Radiologists)",
    "FRCOG (Fellow, Royal College of Obstetricians & Gynaecologists)",
  ],
  "USA Boards": [
    "ABMS Board Certification",
    "FACP (Fellow, American College of Physicians)",
    "FACS (Fellow, American College of Surgeons)",
    "FACOG (Fellow, American College of Obstetricians & Gynaecologists)",
    "FACR (Fellow, American College of Radiology)",
  ],
  "International": [
    "European Board of Medical Specialists (EBMS)",
    "FCFP (Fellow, College of Family Physicians — Canada)",
    "WHO Fellowship",
    "Commonwealth Medical Fellowship",
  ],
};

const SPECIALTIES = [
  "General Practice",
  "Internal Medicine",
  "Surgery",
  "Paediatrics",
  "Obstetrics & Gynaecology",
  "Radiology",
  "Cardiology",
  "Neurology",
  "Oncology",
  "Ophthalmology",
  "Dermatology",
  "Psychiatry",
  "Emergency Medicine",
  "Orthopaedics",
  "Urology",
  "ENT (Ear, Nose & Throat)",
  "Anaesthesiology",
  "Pathology",
  "Other",
];

// ── Step 1: Basic info ────────────────────────────────────────────────────────

function Step1({
  role,
  setRole,
  form,
  setForm,
  onNext,
}: {
  role: "patient" | "doctor";
  setRole: (r: "patient" | "doctor") => void;
  form: { first_name: string; last_name: string; email: string; password: string };
  setForm: (f: typeof form) => void;
  onNext: () => void;
}) {
  const [error, setError] = useState("");

  function set(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm({ ...form, [field]: e.target.value });
  }

  function handleNext(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!form.first_name || !form.last_name || !form.email || !form.password) {
      setError("Please fill in all fields.");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    onNext();
  }

  return (
    <form onSubmit={handleNext} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Input id="first_name" label="First name" placeholder="Ada" value={form.first_name} onChange={set("first_name")} required />
        <Input id="last_name" label="Last name" placeholder="Obi" value={form.last_name} onChange={set("last_name")} required />
      </div>
      <Input id="email" type="email" label="Email address" placeholder="you@example.com" value={form.email} onChange={set("email")} required autoComplete="email" />
      <PasswordInput id="password" label="Password" placeholder="Min 8 chars, 1 uppercase, 1 digit" value={form.password} onChange={set("password")} required autoComplete="new-password" />
      {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
      <Button type="submit" className="w-full" size="lg">
        {role === "doctor" ? "Next: Qualifications →" : "Create account"}
      </Button>
    </form>
  );
}

// ── Step 2: Doctor credentials ────────────────────────────────────────────────

function Step2({
  specialty, setSpecialty,
  licenseNumber, setLicenseNumber,
  qualifications, setQualifications,
  otherQuals, setOtherQuals,
  certFiles, setCertFiles,
  onSubmit,
  loading,
  error,
}: {
  specialty: string; setSpecialty: (v: string) => void;
  licenseNumber: string; setLicenseNumber: (v: string) => void;
  qualifications: string[]; setQualifications: (v: string[]) => void;
  otherQuals: string; setOtherQuals: (v: string) => void;
  certFiles: File[]; setCertFiles: (v: File[]) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean; error: string;
}) {
  function toggleQual(q: string) {
    setQualifications(
      qualifications.includes(q) ? qualifications.filter((x) => x !== q) : [...qualifications, q]
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      {/* Specialty */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-700">Specialty</label>
        <select
          value={specialty}
          onChange={(e) => setSpecialty(e.target.value)}
          className="h-10 w-full rounded-lg border border-gray-300 px-3 text-sm text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
        >
          <option value="">— Select specialty —</option>
          {SPECIALTIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* License number */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-700">Medical licence / registration number</label>
        <input
          value={licenseNumber}
          onChange={(e) => setLicenseNumber(e.target.value)}
          placeholder="e.g. MDCN-12345"
          className="h-10 w-full rounded-lg border border-gray-300 px-3 text-sm text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
        />
      </div>

      {/* Qualifications */}
      <div className="space-y-3">
        <label className="text-sm font-medium text-gray-700">Qualifications & certifications</label>
        <p className="text-xs text-gray-400">Select all that apply.</p>
        <div className="max-h-72 overflow-y-auto rounded-lg border border-gray-200 p-3 space-y-4">
          {Object.entries(QUALIFICATIONS).map(([group, items]) => (
            <div key={group}>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{group}</p>
              <div className="space-y-1.5">
                {items.map((q) => (
                  <label key={q} className="flex items-start gap-2.5 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={qualifications.includes(q)}
                      onChange={() => toggleQual(q)}
                      className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-gray-700 group-hover:text-gray-900">{q}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
        {qualifications.length > 0 && (
          <p className="text-xs text-primary-600 font-medium">{qualifications.length} selected</p>
        )}
      </div>

      {/* Other qualifications */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-700">Other qualifications <span className="text-gray-400 font-normal">(optional)</span></label>
        <textarea
          value={otherQuals}
          onChange={(e) => setOtherQuals(e.target.value)}
          rows={2}
          placeholder="List any additional qualifications not in the list above…"
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100 resize-none"
        />
      </div>

      {/* Certification upload */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-700">
          Upload certifications <span className="text-gray-400 font-normal">(PDF, JPG, PNG — max 5 files, 10 MB each)</span>
        </label>
        <input
          type="file"
          multiple
          accept=".pdf,image/jpeg,image/png"
          onChange={(e) => setCertFiles(Array.from(e.target.files ?? []).slice(0, 5))}
          className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary-50 file:text-primary-700 file:font-medium hover:file:bg-primary-100 cursor-pointer"
        />
        {certFiles.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {certFiles.map((f) => (
              <li key={f.name} className="text-xs text-gray-500 flex items-center gap-1">
                <span className="text-green-500">✓</span> {f.name}
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

      <Button type="submit" loading={loading} className="w-full" size="lg">
        Submit registration
      </Button>

      <p className="text-xs text-gray-400 text-center">
        Your registration will be reviewed by an admin before patients can book consultations.
      </p>
    </form>
  );
}

// ── Main register form ────────────────────────────────────────────────────────

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { login: authLogin } = useAuth();

  const [role, setRole] = useState<"patient" | "doctor">(
    params.get("role") === "doctor" ? "doctor" : "patient",
  );
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", password: "" });

  // Doctor step-2 fields
  const [specialty, setSpecialty] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [qualifications, setQualifications] = useState<string[]>([]);
  const [otherQuals, setOtherQuals] = useState("");
  const [certFiles, setCertFiles] = useState<File[]>([]);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleFinalSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({
        ...form,
        role,
        ...(role === "doctor" && {
          specialty: specialty || undefined,
          license_number: licenseNumber || undefined,
          qualifications,
          other_qualifications: otherQuals || undefined,
        }),
      });
      const { access_token } = await login(form.email, form.password);
      await authLogin(access_token);

      // Upload certs after login (requires auth)
      if (role === "doctor" && certFiles.length > 0) {
        try {
          await uploadCertifications(certFiles);
        } catch {
          // Non-fatal — certs can be submitted later
        }
      }

      if (role === "doctor") {
        router.push("/doctor/pending");
      } else {
        router.push("/patient");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  // For patients, step 1 IS the final submit
  async function handlePatientSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({ ...form, role });
      const { access_token } = await login(form.email, form.password);
      await authLogin(access_token);
      router.push("/patient");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">Create account</h2>

      {/* Role toggle (only on step 1) */}
      {step === 1 && (
        <div className="flex rounded-lg border border-gray-200 p-1 mb-6">
          {(["patient", "doctor"] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => { setRole(r); setStep(1); }}
              className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors capitalize ${
                role === r ? "bg-primary-600 text-white" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      )}

      {/* Step indicator for doctors */}
      {role === "doctor" && (
        <div className="flex items-center gap-2 mb-5">
          {[1, 2].map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`h-6 w-6 rounded-full text-xs font-bold flex items-center justify-center ${s <= step ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-400"}`}>
                {s}
              </div>
              {s < 2 && <div className={`flex-1 h-0.5 w-8 ${step >= 2 ? "bg-primary-600" : "bg-gray-200"}`} />}
            </div>
          ))}
          <span className="text-xs text-gray-500 ml-1">{step === 1 ? "Basic info" : "Qualifications"}</span>
        </div>
      )}

      {step === 1 ? (
        <Step1
          role={role}
          setRole={setRole}
          form={form}
          setForm={setForm}
          onNext={() => {
            if (role === "doctor") {
              setStep(2);
            } else {
              // For patients submit directly
              const fakeEvent = { preventDefault: () => {} } as React.FormEvent;
              handlePatientSubmit(fakeEvent);
            }
          }}
        />
      ) : (
        <Step2
          specialty={specialty} setSpecialty={setSpecialty}
          licenseNumber={licenseNumber} setLicenseNumber={setLicenseNumber}
          qualifications={qualifications} setQualifications={setQualifications}
          otherQuals={otherQuals} setOtherQuals={setOtherQuals}
          certFiles={certFiles} setCertFiles={setCertFiles}
          onSubmit={handleFinalSubmit}
          loading={loading}
          error={error}
        />
      )}

      <p className="mt-4 text-center text-sm text-gray-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary-600 hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  );
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
