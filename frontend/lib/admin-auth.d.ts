export declare const ADMIN_AUTH_PATHS: {
  readonly login: string;
  readonly refresh: string;
  readonly logout: string;
  readonly me: string;
};

export declare const ADMIN_CSRF_COOKIE: string;

export type AdminRequestOptions = {
  cookieHeader?: string;
  csrfToken?: string | null;
};

export declare function readCookieValue(cookieString: string, name: string): string | null;
export declare function readAdminCsrfToken(cookieString?: string): string | null;
export declare function buildAdminRequestInit(
  init?: RequestInit,
  options?: AdminRequestOptions,
): RequestInit;
