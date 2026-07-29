export function getBackendBaseUrl(): string {
  return process.env.BACKEND_BASE_URL ?? "http://127.0.0.1:8000";
}

