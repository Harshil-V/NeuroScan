const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public code: string | undefined,
    message: string
  ) {
    super(message);
  }
}

async function parseError(response: Response): Promise<ApiClientError> {
  let code: string | undefined;
  let detail = response.statusText;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") detail = body.detail;
    if (typeof body.code === "string") code = body.code;
  } catch {
    // non-JSON body; keep statusText
  }
  return new ApiClientError(response.status, code, detail);
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    body: fd,
  });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

export function previewUrl(orthancInstanceId: string): string {
  return `${BASE_URL}/api/instances/${orthancInstanceId}/preview.png`;
}
