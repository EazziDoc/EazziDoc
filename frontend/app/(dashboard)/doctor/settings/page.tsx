"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { deleteMyDoctorAccount, getDoctorProfile, updateDoctorProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";

export default function DoctorSettingsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const { logout } = useAuth();
  const { data: profile, isLoading } = useQuery({
    queryKey: ["doctor-profile"],
    queryFn: getDoctorProfile,
  });

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    specialty: "",
    license_number: "",
  });
  const [isAvailable, setIsAvailable] = useState(true);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (profile) {
      setForm({
        first_name: profile.first_name ?? "",
        last_name: profile.last_name ?? "",
        specialty: profile.specialty ?? "",
        license_number: profile.license_number ?? "",
      });
      setIsAvailable(profile.is_available);
    }
  }, [profile]);

  const { mutateAsync, isPending } = useMutation({
    mutationFn: updateDoctorProfile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doctor-profile"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  function set(field: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      setSaved(false);
    };
  }

  async function handleDeleteAccount() {
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteMyDoctorAccount();
      await logout();
      router.push("/login");
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed. Please try again.");
      setDeleting(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await mutateAsync({
        first_name: form.first_name,
        last_name: form.last_name,
        specialty: form.specialty || null,
        license_number: form.license_number || null,
        is_available: isAvailable,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Update failed");
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
          <CardTitle>Professional information</CardTitle>
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
            id="specialty"
            label="Specialty"
            placeholder="e.g. Radiology, Dermatology"
            value={form.specialty}
            onChange={set("specialty")}
          />

          <Input
            id="license_number"
            label="Medical licence number"
            placeholder="e.g. GH-MD-12345"
            value={form.license_number}
            onChange={set("license_number")}
          />

          {/* Availability toggle */}
          <div className="flex items-center justify-between rounded-xl border border-gray-200 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-gray-900">Available for appointments</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Patients can only book with you when this is on.
              </p>
            </div>
            <button
              type="button"
              onClick={() => { setIsAvailable((v) => !v); setSaved(false); }}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                isAvailable ? "bg-primary-600" : "bg-gray-300"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  isAvailable ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

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

      {!profile?.is_verified && (
        <Card className="border-yellow-200 bg-yellow-50">
          <p className="text-sm text-yellow-800">
            <span className="font-semibold">Account not verified.</span> Your account is pending
            verification by the EazziDoc team. You can still review diagnoses, but patients
            may not be able to book appointments until verification is complete.
          </p>
        </Card>
      )}

      {/* Danger zone */}
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-700">Danger zone</CardTitle>
        </CardHeader>
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            Deleting your account will deactivate your access. Your diagnosis history and patient
            records will be retained for medical record purposes but you will no longer be able to
            log in.
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
        description="Your access will be removed immediately. Your medical records and diagnosis history will be kept. This cannot be undone."
        confirmLabel="Yes, delete my account"
        destructive
        onConfirm={handleDeleteAccount}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
