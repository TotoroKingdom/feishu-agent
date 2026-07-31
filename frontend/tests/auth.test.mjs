import assert from "node:assert/strict";
import test from "node:test";

import {
  ADMIN_AUTH_PATHS,
  buildAdminRequestInit,
  readAdminCsrfToken,
  readCookieValue,
} from "../lib/admin-auth.js";

test("admin auth helpers expose the expected endpoint paths", () => {
  assert.equal(ADMIN_AUTH_PATHS.login, "/api/v1/admin/auth/login");
  assert.equal(ADMIN_AUTH_PATHS.refresh, "/api/v1/admin/auth/refresh");
  assert.equal(ADMIN_AUTH_PATHS.logout, "/api/v1/admin/auth/logout");
  assert.equal(ADMIN_AUTH_PATHS.me, "/api/v1/admin/auth/me");
});

test("admin auth helpers read csrf cookies and attach the header on unsafe requests", () => {
  const cookieString = "theme=dark; admin_csrf_token=csrf-123; session=abc";

  assert.equal(readCookieValue(cookieString, "theme"), "dark");
  assert.equal(readAdminCsrfToken(cookieString), "csrf-123");

  const request = buildAdminRequestInit(
    { method: "POST" },
    { cookieHeader: "session=abc", csrfToken: "csrf-123" },
  );

  assert.equal(request.headers.get("Cookie"), "session=abc");
  assert.equal(request.headers.get("X-CSRF-Token"), "csrf-123");

  const safeRequest = buildAdminRequestInit({ method: "GET" }, { csrfToken: "csrf-123" });
  assert.equal(safeRequest.headers.get("X-CSRF-Token"), null);
});
