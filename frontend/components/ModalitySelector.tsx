"use client";

import { Activity, Eye, Scan } from "lucide-react";

const MODALITIES = [
  {
    key: "chest_xray",
    label: "Chest X-ray",
    description: "Detects 14 pathologies including pneumonia, effusion, and cardiomegaly.",
    Icon: Scan,
    color: "text-blue-600 bg-blue-50",
    selectedColor: "border-blue-500 bg-blue-50",
  },
  {
    key: "fundus",
    label: "Retinal / Fundus",
    description: "Screens for diabetic retinopathy, glaucoma markers, and retinal conditions.",
    Icon: Eye,
    color: "text-violet-600 bg-violet-50",
    selectedColor: "border-violet-500 bg-violet-50",
  },
  {
    key: "skin",
    label: "Skin Lesion",
    description: "Classifies melanoma, nevus, dermatofibroma, and other skin conditions.",
    Icon: Activity,
    color: "text-rose-600 bg-rose-50",
    selectedColor: "border-rose-500 bg-rose-50",
  },
];

interface Props {
  value: string | null;
  onChange: (modality: string) => void;
  disabled?: boolean;
}

export function ModalitySelector({ value, onChange, disabled }: Props) {
  return (
    <div>
      <p className="text-sm font-medium text-gray-700 mb-2">
        Image type <span className="text-red-500">*</span>
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {MODALITIES.map((m) => {
          const selected = value === m.key;
          return (
            <button
              key={m.key}
              type="button"
              disabled={disabled}
              onClick={() => onChange(m.key)}
              className={`flex items-start gap-3 rounded-lg border-2 p-3 text-left transition-colors disabled:opacity-50 ${
                selected
                  ? `${m.selectedColor} border-current`
                  : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <div className={`rounded-lg p-1.5 shrink-0 ${m.color}`}>
                <m.Icon className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">{m.label}</p>
                <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{m.description}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
