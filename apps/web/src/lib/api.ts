type R = Record<string, any>;
export async function api(
  path: string,
  body?: unknown,
  method = "GET",
): Promise<any> {
  const r = await fetch("/api/" + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!r.ok) {
    const v = await r.json().catch(() => ({}));
    throw new Error(
      typeof v.detail === "string"
        ? v.detail
        : Array.isArray(v.detail)
          ? v.detail.map((x: R) => x.msg).join("; ")
          : "Unable to complete the request.",
    );
  }
  return r.status === 204 ? undefined : r.json();
}
