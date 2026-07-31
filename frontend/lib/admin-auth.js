export const ADMIN_AUTH_PATHS = {
  login: "/api/v1/admin/auth/login",
  refresh: "/api/v1/admin/auth/refresh",
  logout: "/api/v1/admin/auth/logout",
  me: "/api/v1/admin/auth/me",
};

export const ADMIN_CSRF_COOKIE = "admin_csrf_token";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function readCookieValue(cookieString, name) {
  if (!cookieString) {
    return null;
  }

  for (const part of cookieString.split(";")) {
    const [rawKey, ...rest] = part.trim().split("=");
    if (rawKey === name) {
      return rest.join("=");
    }
  }

  return null;
}

export function readAdminCsrfToken(cookieString = typeof document === "undefined" ? "" : document.cookie) {
  return readCookieValue(cookieString, ADMIN_CSRF_COOKIE);
}

export function buildAdminRequestInit(init = {}, options = {}) {
  const headers = new Headers(init.headers);
  const method = String(init.method ?? "GET").toUpperCase();

  if (options.cookieHeader) {
    headers.set("Cookie", options.cookieHeader);
  }

  const csrfToken =
    options.csrfToken ?? (typeof document === "undefined" ? null : readAdminCsrfToken());
  if (csrfToken && UNSAFE_METHODS.has(method)) {
    headers.set("X-CSRF-Token", csrfToken);
  }

  return {
    ...init,
    headers,
  };
}
