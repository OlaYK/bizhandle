import axios from "axios";
import type { ApiErrorOut } from "../api/types";

export function getApiErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | (ApiErrorOut & { detail?: string | Array<{ loc?: Array<string | number>; msg?: string }> })
      | undefined;
    if (data?.error?.message) {
      return data.error.message;
    }
    if (typeof data?.detail === "string" && data.detail.trim().length > 0) {
      return data.detail;
    }
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      const firstIssue = data.detail[0];
      const fieldPath = Array.isArray(firstIssue.loc) ? firstIssue.loc.join(".") : "";
      if (firstIssue.msg && fieldPath) {
        return `${fieldPath}: ${firstIssue.msg}`;
      }
      if (firstIssue.msg) {
        return firstIssue.msg;
      }
    }
    if (error.code === "ECONNABORTED") {
      return "Request timed out. Please retry.";
    }
    if (error.code === "ERR_NETWORK") {
      return "Network error. Confirm API URL/CORS and try again.";
    }
    if (error.message) {
      return error.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}
