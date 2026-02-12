import { useRef, useState, type FormEvent } from "react";

import { submitLicense } from "@/api/licenses";
import Button from "@/components/common/Button";
import type { License } from "@/types/license";
import { getApiErrorMessage } from "@/utils/api-error";

interface LicenseFormProps {
  onSubmitted?: (license: License) => void;
}

const US_STATES: Array<{ code: string; label: string }> = [
  { code: "AL", label: "Alabama" },
  { code: "AK", label: "Alaska" },
  { code: "AZ", label: "Arizona" },
  { code: "AR", label: "Arkansas" },
  { code: "CA", label: "California" },
  { code: "CO", label: "Colorado" },
  { code: "CT", label: "Connecticut" },
  { code: "DE", label: "Delaware" },
  { code: "FL", label: "Florida" },
  { code: "GA", label: "Georgia" },
  { code: "HI", label: "Hawaii" },
  { code: "ID", label: "Idaho" },
  { code: "IL", label: "Illinois" },
  { code: "IN", label: "Indiana" },
  { code: "IA", label: "Iowa" },
  { code: "KS", label: "Kansas" },
  { code: "KY", label: "Kentucky" },
  { code: "LA", label: "Louisiana" },
  { code: "ME", label: "Maine" },
  { code: "MD", label: "Maryland" },
  { code: "MA", label: "Massachusetts" },
  { code: "MI", label: "Michigan" },
  { code: "MN", label: "Minnesota" },
  { code: "MS", label: "Mississippi" },
  { code: "MO", label: "Missouri" },
  { code: "MT", label: "Montana" },
  { code: "NE", label: "Nebraska" },
  { code: "NV", label: "Nevada" },
  { code: "NH", label: "New Hampshire" },
  { code: "NJ", label: "New Jersey" },
  { code: "NM", label: "New Mexico" },
  { code: "NY", label: "New York" },
  { code: "NC", label: "North Carolina" },
  { code: "ND", label: "North Dakota" },
  { code: "OH", label: "Ohio" },
  { code: "OK", label: "Oklahoma" },
  { code: "OR", label: "Oregon" },
  { code: "PA", label: "Pennsylvania" },
  { code: "RI", label: "Rhode Island" },
  { code: "SC", label: "South Carolina" },
  { code: "SD", label: "South Dakota" },
  { code: "TN", label: "Tennessee" },
  { code: "TX", label: "Texas" },
  { code: "UT", label: "Utah" },
  { code: "VT", label: "Vermont" },
  { code: "VA", label: "Virginia" },
  { code: "WA", label: "Washington" },
  { code: "WV", label: "West Virginia" },
  { code: "WI", label: "Wisconsin" },
  { code: "WY", label: "Wyoming" },
];

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

const LicenseForm = ({ onSubmitted }: LicenseFormProps) => {
  const [stateCode, setStateCode] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [licenseType, setLicenseType] = useState("");
  const [document, setDocument] = useState<File | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const resetForm = () => {
    setStateCode("");
    setLicenseNumber("");
    setLicenseType("");
    setDocument(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const validateFile = (file: File): string | null => {
    const isPdf = file.type === "application/pdf";
    const isImage = file.type.startsWith("image/");
    if (!isPdf && !isImage) {
      return "Document must be a PDF or image file.";
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      return "Document must be 10 MB or smaller.";
    }

    return null;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSuccessMessage(null);
    setErrorMessage(null);

    const normalizedState = stateCode.trim().toUpperCase();
    const normalizedLicenseNumber = licenseNumber.trim();

    if (!normalizedState) {
      setErrorMessage("State is required.");
      return;
    }

    if (!normalizedLicenseNumber) {
      setErrorMessage("License number is required.");
      return;
    }

    if (!document) {
      setErrorMessage("Please upload a license document.");
      return;
    }

    const fileError = validateFile(document);
    if (fileError) {
      setErrorMessage(fileError);
      return;
    }

    const formData = new FormData();
    formData.append("state", normalizedState);
    formData.append("license_number", normalizedLicenseNumber);

    if (licenseType.trim()) {
      formData.append("license_type", licenseType.trim());
    }

    formData.append("document", document);

    setSubmitting(true);

    try {
      const created = await submitLicense(formData);
      setSuccessMessage("License submitted successfully.");
      resetForm();
      onSubmitted?.(created);
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(error, "Unable to submit license. Please try again."),
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-3xl border border-[#d9e4f8] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]"
    >
      <div>
        <h2 className="text-xl font-semibold text-[#0a1633]">Submit License</h2>
        <p className="mt-1 text-sm text-[#4c628a]">
          Upload your state license for verification.
        </p>
      </div>

      {successMessage && (
        <div className="rounded-xl border border-[#b7ebc6] bg-[#ebfff1] px-3 py-2 text-sm text-[#0f5132]">
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="rounded-xl border border-[#ffd6d2] bg-[#fff2f0] px-3 py-2 text-sm text-[#8a1d1d]">
          {errorMessage}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm font-medium text-[#0a1633]">
          <span>State</span>
          <select
            value={stateCode}
            onChange={(event) => setStateCode(event.target.value)}
            className="w-full rounded-xl border border-[#d9e4f8] px-3 py-2 text-sm text-[#0a1633] focus:border-[#8ea4d8] focus:outline-none"
            required
          >
            <option value="">Select state</option>
            {US_STATES.map((state) => (
              <option key={state.code} value={state.code}>
                {state.label} ({state.code})
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1 text-sm font-medium text-[#0a1633]">
          <span>License number</span>
          <input
            type="text"
            value={licenseNumber}
            onChange={(event) => setLicenseNumber(event.target.value)}
            className="w-full rounded-xl border border-[#d9e4f8] px-3 py-2 text-sm text-[#0a1633] focus:border-[#8ea4d8] focus:outline-none"
            placeholder="Enter license number"
            required
          />
        </label>
      </div>

      <label className="space-y-1 text-sm font-medium text-[#0a1633]">
        <span>License type (optional)</span>
        <input
          type="text"
          value={licenseType}
          onChange={(event) => setLicenseType(event.target.value)}
          className="w-full rounded-xl border border-[#d9e4f8] px-3 py-2 text-sm text-[#0a1633] focus:border-[#8ea4d8] focus:outline-none"
          placeholder="Example: Series 65, Insurance Producer"
        />
      </label>

      <label className="space-y-1 text-sm font-medium text-[#0a1633]">
        <span>Document upload (PDF or image)</span>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,image/*"
          onChange={(event) => setDocument(event.target.files?.[0] ?? null)}
          className="w-full rounded-xl border border-[#d9e4f8] px-3 py-2 text-sm text-[#0a1633] file:mr-3 file:rounded-full file:border-0 file:bg-[#eaf1ff] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-[#0a1633]"
          required
        />
      </label>

      <div className="pt-1">
        <Button type="submit" loading={submitting} className="w-full sm:w-auto">
          {submitting ? "Submitting..." : "Submit License"}
        </Button>
      </div>
    </form>
  );
};

export default LicenseForm;
