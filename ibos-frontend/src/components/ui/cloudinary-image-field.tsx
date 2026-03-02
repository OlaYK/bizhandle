import { type ChangeEvent, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "./button";
import { useToast } from "../../hooks/use-toast";
import { uploadImageToCloudinary } from "../../lib/cloudinary";
import { cn } from "../../lib/cn";

interface CloudinaryImageFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  folder?: string;
  previewAlt?: string;
  disabled?: boolean;
}

export function CloudinaryImageField({
  label,
  value,
  onChange,
  placeholder,
  folder,
  previewAlt,
  disabled = false
}: CloudinaryImageFieldProps) {
  const { showToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      showToast({
        title: "Invalid file type",
        description: "Select an image file.",
        variant: "error"
      });
      event.target.value = "";
      return;
    }

    if (file.size > 8 * 1024 * 1024) {
      showToast({
        title: "File too large",
        description: "Image must be 8MB or less.",
        variant: "error"
      });
      event.target.value = "";
      return;
    }

    setUploading(true);
    try {
      const uploadedUrl = await uploadImageToCloudinary(file, { folder });
      onChange(uploadedUrl);
      showToast({
        title: "Image uploaded",
        description: "Cloudinary URL saved.",
        variant: "success"
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Image upload failed.";
      showToast({
        title: "Upload failed",
        description: message,
        variant: "error"
      });
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-semibold text-surface-700 dark:text-surface-100">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(
          "h-11 w-full rounded-lg border border-surface-200 bg-white px-3 text-sm text-surface-800 shadow-sm outline-none transition placeholder:text-surface-400 focus:border-surface-400 focus:ring-2 focus:ring-surface-200 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100 dark:placeholder:text-surface-300 dark:focus:border-surface-300 dark:focus:ring-surface-600",
          disabled ? "opacity-70" : ""
        )}
      />
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={handleUpload}
          className="hidden"
          disabled={disabled || uploading}
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          loading={uploading}
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
        >
          <Upload className="h-4 w-4" />
          Upload image
        </Button>
        {value ? (
          <a
            href={value}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-semibold text-cobalt-700 underline decoration-dotted underline-offset-4"
          >
            Open image
          </a>
        ) : null}
      </div>
      {value ? (
        <img
          src={value}
          alt={previewAlt || label}
          className="h-24 w-full rounded-lg border border-surface-200 bg-surface-50 object-cover"
        />
      ) : null}
    </label>
  );
}
