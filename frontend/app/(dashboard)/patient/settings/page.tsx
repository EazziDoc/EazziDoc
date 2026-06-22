"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, Clock, AlertCircle } from "lucide-react";
import { deleteMyAccount, getPatientProfile, submitPatientIdentity, updatePatientProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";

export default function PatientSettingsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const { logout } = useAuth();

  const { data: profile, isLoading } = useQuery({
    queryKey: ["patient-profile"],
    queryFn: getPatientProfile,
  });

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    date_of_birth: "",
    gender: "",
    phone: "",
    country: "",
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);

  // Identity verification state
  const [idType, setIdType] = useState("national_id");
  const [idNumber, setIdNumber] = useState("");
  const [idFile, setIdFile] = useState<File | null>(null);
  const [idSubmitting, setIdSubmitting] = useState(false);
  const [idError, setIdError] = useState("");
  const [idSuccess, setIdSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (profile) {
      setForm({
        first_name: profile.first_name ?? "",
        last_name: profile.last_name ?? "",
        date_of_birth: profile.date_of_birth ?? "",
        gender: profile.gender ?? "",
        phone: profile.phone ?? "",
        country: profile.country ?? "",
      });
    }
  }, [profile]);

  const { mutateAsync, isPending } = useMutation({
    mutationFn: updatePatientProfile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patient-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  function set(field: string) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      setSaved(false);
    };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await mutateAsync({
        first_name: form.first_name,
        last_name: form.last_name,
        date_of_birth: form.date_of_birth || null,
        gender: form.gender || null,
        phone: form.phone || null,
        country: form.country || null,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function handleIdentitySubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!idFile) { setIdError("Please select a document file."); return; }
    setIdError("");
    setIdSubmitting(true);
    try {
      await submitPatientIdentity(idType, idNumber, idFile);
      qc.invalidateQueries({ queryKey: ["patient-profile"] });
      setIdSuccess(true);
      setIdNumber("");
      setIdFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err: unknown) {
      setIdError(err instanceof Error ? err.message : "Submission failed. Please try again.");
    } finally {
      setIdSubmitting(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteMyAccount();
      await logout();
      router.push("/login");
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed. Please try again.");
      setDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="h-7 w-7 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Profile settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Personal information</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <Input
              id="first_name"
              label="First name"
              value={form.first_name}
              onChange={set("first_name")}
              required
            />
            <Input
              id="last_name"
              label="Last name"
              value={form.last_name}
              onChange={set("last_name")}
              required
            />
          </div>

          <Input
            id="date_of_birth"
            type="date"
            label="Date of birth"
            value={form.date_of_birth}
            onChange={set("date_of_birth")}
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
            <select
              value={form.gender}
              onChange={set("gender")}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              <option value="">Prefer not to say</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="non_binary">Non-binary</option>
              <option value="prefer_not_to_say">Prefer not to say</option>
            </select>
          </div>

          <Input
            id="phone"
            type="tel"
            label="Phone number"
            placeholder="+233 XX XXX XXXX"
            value={form.phone}
            onChange={set("phone")}
          />

          <Input
            id="country"
            label="Country"
            placeholder="Ghana"
            value={form.country}
            onChange={set("country")}
          />

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          {saved && (
            <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">
              Profile updated successfully.
            </p>
          )}

          <Button type="submit" loading={isPending}>
            Save changes
          </Button>
        </form>
      </Card>

      {/* Identity verification */}
      <div id="identity-verification">
      <Card>
        <CardHeader>
          <CardTitle>Identity verification</CardTitle>
        </CardHeader>

        {profile?.identity_verification_status === "verified" && (
          <div className="flex items-center gap-2 text-green-700 bg-green-50 rounded-lg px-3 py-2 text-sm">
            <CheckCircle className="h-4 w-4 shrink-0" />
            Identity verified
            {profile.id_verified_at && (
              <span className="text-green-600 ml-1">
                — {new Date(profile.id_verified_at).toLocaleDateString()}
              </span>
            )}
          </div>
        )}

        {profile?.identity_verification_status === "pending_review" && (
          <div className="flex items-center gap-2 text-blue-700 bg-blue-50 rounded-lg px-3 py-2 text-sm">
            <Clock className="h-4 w-4 shrink-0" />
            Under review — we'll notify you once approved.
          </div>
        )}

        {(profile?.identity_verification_status === "unverified" ||
          profile?.identity_verification_status === "rejected") && (
          <div className="space-y-4">
            {profile.identity_verification_status === "rejected" && (
              <div className="flex items-start gap-2 text-red-700 bg-red-50 rounded-lg px-3 py-2 text-sm">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <div>
                  <span className="font-medium">Rejected:</span>{" "}
                  {profile.id_rejection_reason ?? "See rejection notice above."}
                </div>
              </div>
            )}
            <p className="text-sm text-gray-500">
              Submit a government-issued ID to verify your identity. Accepted: PDF, JPEG, PNG (max 10 MB).
            </p>
            <form onSubmit={handleIdentitySubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ID type</label>
                <select
                  value={idType}
                  onChange={(e) => setIdType(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="national_id">National ID</option>
                  <option value="passport">Passport</option>
                  <option value="drivers_license">Driver&apos;s licence</option>
                </select>
              </div>
              <Input
                id="id_number"
                label="ID number"
                placeholder="e.g. GHA-123456789-0"
                value={idNumber}
                onChange={(e) => setIdNumber(e.target.value)}
                required
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Document scan / photo</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  required
                  onChange={(e) => setIdFile(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-gray-700 file:mr-3 file:rounded-lg file:border-0 file:bg-primary-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary-700 hover:file:bg-primary-100"
                />
              </div>
              {idError && (
                <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{idError}</p>
              )}
              {idSuccess && (
                <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">
                  Submitted for review. You&apos;ll be notified once approved.
                </p>
              )}
              <Button type="submit" loading={idSubmitting}>
                Submit for verification
              </Button>
            </form>
          </div>
        )}
      </Card>
      </div>

      {/* Danger zone */}
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-700">Danger zone</CardTitle>
        </CardHeader>
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            Deleting your account will deactivate your access. Your diagnosis history will be
            retained for medical record purposes but you will no longer be able to log in.
          </p>
          {deleteError && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{deleteError}</p>
          )}
          <Button
            variant="destructive"
            size="sm"
            loading={deleting}
            onClick={() => setConfirmDelete(true)}
          >
            Delete my account
          </Button>
        </div>
      </Card>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete your account?"
        description="Your access will be removed immediately. Your medical diagnosis history will be kept for record purposes. This cannot be undone."
        confirmLabel="Yes, delete my account"
        destructive
        onConfirm={handleDeleteAccount}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
