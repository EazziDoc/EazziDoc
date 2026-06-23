"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { createDiagnosis, uploadImages } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { ModalitySelector } from "@/components/ModalitySelector";

const ACCEPTED = ["image/jpeg", "image/png", "image/tiff", "application/dicom"];
const MAX_FILES = 5;
const MAX_MB = 10;

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [modality, setModality] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [step, setStep] = useState<"select" | "uploading" | "creating">("select");

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    const valid = selected.filter(
      (f) => ACCEPTED.includes(f.type) && f.size <= MAX_MB * 1024 * 1024,
    );
    if (valid.length !== selected.length) {
      setError("Some files were skipped (wrong type or over 10 MB).");
    } else {
      setError("");
    }
    setFiles((prev) => [...prev, ...valid].slice(0, MAX_FILES));
  }

  function removeFile(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) { setError("Add at least one image."); return; }
    if (!modality) { setError("Select an image type."); return; }
    setError("");
    setStep("uploading");
    try {
      const { uploaded } = await uploadImages(files);
      setStep("creating");
      const diagnosis = await createDiagnosis({
        image_keys: uploaded.map((u) => u.image_key),
        modality: modality!,
        patient_notes: notes.trim() || undefined,
      });
      router.push(`/patient/diagnoses/${diagnosis.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setStep("select");
    }
  }

  const busy = step !== "select";

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">New diagnosis</h1>
        <p className="text-gray-500 mt-1">
          Select the image type, upload your scan, and our AI will analyse it.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <ModalitySelector value={modality} onChange={setModality} disabled={busy} />

        {/* Drop zone */}
        <Card
          className="border-2 border-dashed border-gray-300 text-center cursor-pointer hover:border-primary-400 transition-colors"
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPTED.join(",")}
            onChange={onFileChange}
            className="hidden"
          />
          <div className="py-8">
            <p className="text-sm font-medium text-gray-700">
              Click to select images
            </p>
            <p className="text-xs text-gray-400 mt-1">
              JPEG, PNG, TIFF, DICOM · max 10 MB each · up to {MAX_FILES} images
            </p>
          </div>
        </Card>

        {/* File list */}
        {files.length > 0 && (
          <ul className="space-y-2">
            {files.map((f, i) => (
              <li
                key={i}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-2"
              >
                <span className="text-sm text-gray-700 truncate max-w-xs">{f.name}</span>
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  className="text-gray-400 hover:text-red-500 ml-4 text-xs"
                  disabled={busy}
                >
                  remove
                </button>
              </li>
            ))}
          </ul>
        )}

        <Textarea
          id="notes"
          label="Patient notes (optional)"
          placeholder="Describe your symptoms, duration, or any relevant history…"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={busy}
        />

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}

        <Button
          type="submit"
          loading={busy}
          disabled={files.length === 0 || !modality || busy}
          size="lg"
          className="w-full"
        >
          {step === "uploading"
            ? "Uploading images…"
            : step === "creating"
              ? "Starting AI analysis…"
              : `Submit ${files.length > 0 ? `(${files.length} image${files.length > 1 ? "s" : ""})` : ""}`}
        </Button>
      </form>
    </div>
  );
}
