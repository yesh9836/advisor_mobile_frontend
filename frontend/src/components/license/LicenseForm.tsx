import { useRef, useState, type SubmitEvent } from "react";

import { submitLicense } from "@/api/licenses";
import Button from "@/components/common/Button";
import {
  LICENSE_DOCUMENT_ACCEPT,
  validateLicenseDocument,
} from "@/components/license/documentUpload";
import { US_STATE_OPTIONS } from "@/lib/usStates";
import type { License } from "@/types/license";
import { getApiErrorMessage } from "@/utils/api-error";

interface LicenseFormProps {
  onSubmitted?: (license: License) => void;
}

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

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
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

    const fileError = validateLicenseDocument(document);
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
            {US_STATE_OPTIONS.map((state) => (
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
          placeholder="Enter license type"
        />
      </label>

      <label className="space-y-1 text-sm font-medium text-[#0a1633]">
        <span>Document upload (PDF, JPG, JPEG, or PNG)</span>
        <input
          ref={fileInputRef}
          type="file"
          accept={LICENSE_DOCUMENT_ACCEPT}
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
