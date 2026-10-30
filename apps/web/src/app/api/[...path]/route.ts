import { NextRequest, NextResponse } from "next/server";
import { valid, sameOrigin, COOKIE } from "@/lib/session";
const id = "[a-f0-9-]{36}";
const allowed = new RegExp(
  `^(ready|profile|profile-import|profile/(?:experience|education|skills|projects|certifications|languages|identity|rules)(?:/${id})?|preferences|roles|applications(?:/${id}(?:/(?:job|stage|verification|notes|documents|evidence))?)?|jobs|templates|documents/${id}(?:/approve|/download/(?:docx|pdf|txt))?|evidence/${id}/download|employers(?:/${id})?|sources(?:/bootstrap|/feeds(?:/${id}(?:/verify)?)?)?|search|capture|saved-searches(?:/${id}(?:/run)?)?|activity|reminders(?:/${id}/complete)?|tracker/export|storage)$`,
);
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  if (!valid(request.cookies.get(COOKIE)?.value))
    return NextResponse.json(
      { detail: "Use the Start file to unlock this private app." },
      { status: 401 },
    );
  if (request.method !== "GET" && !sameOrigin(request))
    return NextResponse.json(
      { detail: "Invalid request origin" },
      { status: 403 },
    );
  const path = (await context.params).path.join("/");
  if (!allowed.test(path))
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  try {
    const base = process.env.API_BASE_URL,
      token = process.env.API_TOKEN;
    if (!base || !token) throw new Error();
    const body = request.method === "GET" ? undefined : await request.text();
    if (
      body &&
      Buffer.byteLength(body) > (path.endsWith("/evidence") ? 7100000 : 220000)
    )
      return NextResponse.json(
        { detail: "Request too large" },
        { status: 413 },
      );
    const response = await fetch(
      `${base}/api/${path}${path.endsWith("/run") ? "?offset=" + Number(request.nextUrl.searchParams.get("offset") || 0) : ""}`,
      {
        method: request.method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(200000),
      },
    );
    return new NextResponse(response.status === 204 ? null : response.body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") || "application/json",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        ...(response.headers.has("Content-Disposition")
          ? {
              "Content-Disposition": response.headers.get(
                "Content-Disposition",
              )!,
            }
          : {}),
      },
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "The local service is unavailable. Check the Start window and data/logs.",
      },
      { status: 503 },
    );
  }
}
export const GET = proxy,
  POST = proxy,
  PUT = proxy,
  DELETE = proxy;
