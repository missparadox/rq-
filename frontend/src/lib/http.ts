async function buildRequestError(response: Response): Promise<Error> {
  const body = await response.text().catch(() => "");
  const suffix = body.trim() ? `: ${body}` : "";
  return new Error(`Request failed: ${response.status}${suffix}`);
}

export async function postForm<T>(url: string, formData: FormData): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await buildRequestError(response);
  }

  return response.json() as Promise<T>;
}

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw await buildRequestError(response);
  }

  return response.json() as Promise<T>;
}

export async function postJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
  });

  if (!response.ok) {
    throw await buildRequestError(response);
  }

  return response.json() as Promise<T>;
}
