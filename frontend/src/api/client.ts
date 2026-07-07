const BASE_URL = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8123";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const url = new URL(BASE_URL + path);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; params?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const response = await fetch(buildUrl(path, options.params), {
    method,
    headers: options.body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail ?? data;
    } catch {
      // resposta sem corpo JSON (ex: 500 generico)
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>("GET", path, { params }),
  post: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>("POST", path, { body, params }),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, { body }),
  patch: <T>(path: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>("PATCH", path, { body, params }),
  delete: <T>(path: string) => request<T>("DELETE", path),
  downloadUrl: (path: string, params?: Record<string, string | number | boolean | undefined>) =>
    buildUrl(path, params),
};
