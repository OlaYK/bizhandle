/**
 * Utility functions for generating standard SKUs from product and variant metadata.
 */

export function cleanSkuSegment(text?: string, maxLen = 4): string {
  if (!text) return "";
  const trimmed = text.trim();
  if (!trimmed) return "";

  // If already short alphanumeric code (e.g. "6x6", "XL", "M", "S", "42")
  const directClean = trimmed.toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (directClean.length <= maxLen && directClean.length > 0) {
    return directClean;
  }

  // Multi-word acronym: "Blue Cotton T-Shirt" -> "BCT"
  const words = trimmed.toUpperCase().split(/[\s\-_/]+/).filter(Boolean);
  if (words.length > 1) {
    const acronym = words
      .map((w) => w.replace(/[^A-Z0-9]/g, "")[0])
      .filter(Boolean)
      .join("");
    if (acronym.length >= 2) {
      return acronym.slice(0, maxLen);
    }
  }

  // Single word: remove vowels after first char if > maxLen, e.g. "PLAIN" -> "PLN", "ANKARA" -> "ANK"
  if (directClean.length > maxLen) {
    const noVowels =
      directClean[0] + directClean.slice(1).replace(/[AEIOU]/g, "");
    if (noVowels.length >= 3) {
      return noVowels.slice(0, maxLen);
    }
  }

  return directClean.slice(0, maxLen);
}

export interface GenerateSkuOptions {
  productName?: string;
  size?: string;
  label?: string;
}

export function generateSku({
  productName,
  size,
  label,
}: GenerateSkuOptions): string {
  const parts: string[] = [];

  const cleanProd = cleanSkuSegment(
    productName === "No product selected" ? "" : productName,
    3,
  );
  if (cleanProd) parts.push(cleanProd);

  const cleanSz = cleanSkuSegment(size, 4);
  if (cleanSz) parts.push(cleanSz);

  const cleanLbl = cleanSkuSegment(label, 3);
  if (cleanLbl) parts.push(cleanLbl);

  return parts.join("-");
}
