interface CloudinaryUploadOptions {
  folder?: string;
}

interface CloudinaryUploadResponse {
  secure_url?: string;
  error?: {
    message?: string;
  };
}

function getRequiredEnvValue(name: "VITE_CLOUDINARY_CLOUD_NAME" | "VITE_CLOUDINARY_UPLOAD_PRESET") {
  const value = import.meta.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is not configured.`);
  }
  return value;
}

export async function uploadImageToCloudinary(file: File, options?: CloudinaryUploadOptions) {
  const cloudName = getRequiredEnvValue("VITE_CLOUDINARY_CLOUD_NAME");
  const uploadPreset = getRequiredEnvValue("VITE_CLOUDINARY_UPLOAD_PRESET");
  const endpoint = `https://api.cloudinary.com/v1_1/${cloudName}/image/upload`;

  const payload = new FormData();
  payload.append("file", file);
  payload.append("upload_preset", uploadPreset);

  const folder = options?.folder ?? import.meta.env.VITE_CLOUDINARY_FOLDER?.trim();
  if (folder) {
    payload.append("folder", folder);
  }

  const response = await fetch(endpoint, {
    method: "POST",
    body: payload
  });
  const data = (await response.json()) as CloudinaryUploadResponse;

  if (!response.ok) {
    throw new Error(data.error?.message || "Image upload failed.");
  }

  if (!data.secure_url) {
    throw new Error("Image upload completed without a secure URL.");
  }

  return data.secure_url;
}
