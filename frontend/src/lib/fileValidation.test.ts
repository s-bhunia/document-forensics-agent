import { describe, expect, it } from "vitest";
import { MAX_FILE_BYTES, fileExtension, validateFile } from "./fileValidation";

const f = (name: string, size = 1000, type = "") => ({ name, size, type });

describe("validateFile", () => {
  it.each(["a.png", "b.JPG", "c.jpeg", "d.webp", "e.tif", "f.TIFF", "g.bmp", "h.pdf", "i.docx"])(
    "accepts %s",
    (name) => {
      expect(validateFile(f(name))).toEqual({ ok: true });
    },
  );

  it.each(["notes.txt", "sheet.xlsx", "old.doc", "archive.zip", "noextension"])("rejects %s", (name) => {
    const r = validateFile(f(name));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/unsupported file type/i);
  });

  it("ignores misleading MIME types and trusts the extension", () => {
    expect(validateFile(f("scan.tiff", 10, "")).ok).toBe(true);
    expect(validateFile(f("evil.exe", 10, "image/png")).ok).toBe(false);
  });

  it("accepts exactly 25 MB and rejects anything larger", () => {
    expect(validateFile(f("a.pdf", MAX_FILE_BYTES)).ok).toBe(true);
    const r = validateFile(f("a.pdf", MAX_FILE_BYTES + 1));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/too large.*25 MB/i);
  });

  it("rejects empty files", () => {
    const r = validateFile(f("a.png", 0));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/empty/i);
  });
});

describe("fileExtension", () => {
  it("returns the lowercased last extension", () => {
    expect(fileExtension("My.Scan.PDF")).toBe(".pdf");
    expect(fileExtension("README")).toBe("");
  });
});
