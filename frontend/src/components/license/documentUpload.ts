const LICENSE_DOCUMENT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

const LICENSE_DOCUMENT_ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"] as const;

const LICENSE_DOCUMENT_ALLOWED_MIME_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/jpg",
  "image/png",
] as const;

const allowedExtensions = new Set<string>(LICENSE_DOCUMENT_ALLOWED_EXTENSIONS);
const allowedMimeTypes = new Set<string>(LICENSE_DOCUMENT_ALLOWED_MIME_TYPES);

export const LICENSE_DOCUMENT_ACCEPT = [
  ...LICENSE_DOCUMENT_ALLOWED_MIME_TYPES,
  ...LICENSE_DOCUMENT_ALLOWED_EXTENSIONS,
].join(",");

const getFileExtension = (filename: string): string => {
  const trimmedName = filename.trim().toLowerCase();
  const extensionStart = trimmedName.lastIndexOf(".");
  if (extensionStart < 0) {
    return "";
  }
  return trimmedName.slice(extensionStart);
};

export const validateLicenseDocument = (file: File): string | null => {
  const contentType = file.type.trim().toLowerCase();
  const extension = getFileExtension(file.name);

  const hasAllowedExtension = allowedExtensions.has(extension);
  const hasAllowedContentType = contentType ? allowedMimeTypes.has(contentType) : true;

  if (!hasAllowedExtension || !hasAllowedContentType) {
    return "Document must be a PDF, JPG, JPEG, or PNG file.";
  }

  if (file.size > LICENSE_DOCUMENT_MAX_FILE_SIZE_BYTES) {
    return "Document must be 10 MB or smaller.";
  }

  return null;
};
