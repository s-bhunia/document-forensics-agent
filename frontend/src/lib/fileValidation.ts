export const MAX_FILE_BYTES = 25 * 1024 * 1024;

export const ACCEPTED_EXTENSIONS = [
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".tif",
  ".tiff",
  ".bmp",
  ".pdf",
  ".docx",
] as const;

export const ACCEPTED_MIME_TYPES = [
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/tiff",
  "image/bmp",
  "image/x-ms-bmp",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
] as const;

/** Value for an <input type="file" accept> attribute. */
export const ACCEPT_ATTR = [...ACCEPTED_EXTENSIONS, ...ACCEPTED_MIME_TYPES].join(",");

export type FileValidationResult = { ok: true } | { ok: false; error: string };

export function fileExtension(name: string): string {
  const idx = name.lastIndexOf(".");
  return idx >= 0 ? name.slice(idx).toLowerCase() : "";
}

/** Extension is authoritative because browsers often report empty or generic MIME types (e.g. TIFF, DOCX). */
export function validateFile(file: Pick<File, "name" | "size" | "type">): FileValidationResult {
  const ext = fileExtension(file.name);
  if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(ext)) {
    return {
      ok: false,
      error: `Unsupported file type${ext ? ` "${ext}"` : ""}. Upload an image (PNG, JPG, WEBP, TIFF, BMP), PDF or DOCX.`,
    };
  }
  if (file.size === 0) {
    return { ok: false, error: "This file is empty." };
  }
  if (file.size > MAX_FILE_BYTES) {
    const mb = (file.size / (1024 * 1024)).toFixed(1);
    return { ok: false, error: `File is too large (${mb} MB). The maximum size is 25 MB.` };
  }
  return { ok: true };
}

export const MAX_BATCH_FILES = 20;

export interface RejectedFile {
  name: string;
  error: string;
}

export interface BatchValidation {
  accepted: File[];
  rejected: RejectedFile[];
}

/** Validates each file and caps the selection (including files already selected) at MAX_BATCH_FILES. */
export function validateFiles(files: File[], alreadySelected = 0): BatchValidation {
  const accepted: File[] = [];
  const rejected: RejectedFile[] = [];
  for (const file of files) {
    const result = validateFile(file);
    if (!result.ok) {
      rejected.push({ name: file.name, error: result.error });
    } else if (alreadySelected + accepted.length >= MAX_BATCH_FILES) {
      rejected.push({ name: file.name, error: `Only ${MAX_BATCH_FILES} files can be analyzed at once.` });
    } else {
      accepted.push(file);
    }
  }
  return { accepted, rejected };
}
