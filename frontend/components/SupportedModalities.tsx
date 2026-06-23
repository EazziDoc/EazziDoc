import { Activity, Eye, Scan } from "lucide-react";
import { Card } from "@/components/ui/card";

const MODALITIES = [
  {
    icon: Scan,
    label: "Chest X-ray",
    description: "Detects 14 pathologies including pneumonia, effusion, cardiomegaly, and pneumothorax.",
    color: "text-blue-600 bg-blue-50",
  },
  {
    icon: Eye,
    label: "Retinal / Fundus",
    description: "Screens for diabetic retinopathy, glaucoma markers, and other retinal conditions.",
    color: "text-violet-600 bg-violet-50",
  },
  {
    icon: Activity,
    label: "Skin conditions",
    description: "Classifies common dermatological conditions including melanoma, nevus, and dermatofibroma.",
    color: "text-rose-600 bg-rose-50",
  },
];

export function SupportedModalities() {
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-gray-900">Supported imaging types</h2>
        <span className="text-xs font-medium text-primary-600 bg-primary-50 px-2 py-1 rounded-full">
          AI-powered
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {MODALITIES.map((m) => (
          <div
            key={m.label}
            className="flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50 p-3"
          >
            <div className={`rounded-lg p-2 shrink-0 ${m.color}`}>
              <m.icon className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">{m.label}</p>
              <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{m.description}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
