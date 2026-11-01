import clsx from "clsx";
import { useId, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { UploadCloud } from "lucide-react";
import { ACCEPT_ATTR, MAX_BATCH_FILES } from "../lib/fileValidation";

interface Props {
  onFiles: (files: File[]) => void;
  multiple?: boolean;
  disabled?: boolean;
  invalid?: boolean;
  describedBy?: string;
}

export function Dropzone({ onFiles, multiple = true, disabled, invalid, describedBy }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const hintId = useId();

  const open = () => {
    if (!disabled) inputRef.current?.click();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      open();
    }
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!disabled) setDragging(true);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const files = Array.from(e.dataTransfer.files ?? []);
    if (files.length > 0) onFiles(multiple ? files : files.slice(0, 1));
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled || undefined}
      aria-label={multiple ? "Choose documents to analyze, or drag and drop them here" : "Choose a document to analyze, or drag and drop it here"}
      aria-describedby={clsx(hintId, describedBy) || undefined}
      onClick={open}
      onKeyDown={onKeyDown}
      onDragOver={onDragOver}
      onDragEnter={onDragOver}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      data-dragging={dragging || undefined}
      className={clsx(
        "group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-colors sm:py-16",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 dark:focus-visible:ring-offset-slate-950",
        dragging
          ? "border-indigo-500 bg-indigo-50/70 dark:bg-indigo-500/10"
          : invalid
            ? "border-red-300 bg-white hover:border-red-400 dark:border-red-500/50 dark:bg-slate-900"
            : "border-slate-300 bg-white hover:border-indigo-400 hover:bg-indigo-50/30 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-indigo-500/60 dark:hover:bg-indigo-500/5",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-50 text-indigo-600 transition-transform group-hover:scale-105 dark:bg-indigo-500/10 dark:text-indigo-400">
        <UploadCloud className="h-7 w-7" aria-hidden="true" />
      </div>
      <p className="mt-4 text-base font-medium">
        <span className="text-indigo-600 dark:text-indigo-400">Click to browse</span> or drag and drop
      </p>
      <p id={hintId} className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        PNG, JPG, WEBP, TIFF, BMP, PDF or DOCX · up to 25 MB each{multiple && ` · up to ${MAX_BATCH_FILES} files`}
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        multiple={multiple}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="file-input"
        disabled={disabled}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length > 0) onFiles(files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
