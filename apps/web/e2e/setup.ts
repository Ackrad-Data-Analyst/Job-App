import { request } from "@playwright/test";
import { mkdir } from "node:fs/promises";
export default async function setup() {
  await mkdir("test-results", { recursive: true });
  const r = await request.newContext({ baseURL: "http://127.0.0.1:3100" });
  const result = await r.post("/api/unlock", {
    headers: { Origin: "http://127.0.0.1:3100" },
    data: { code: "browser-fixture-code-000000000000000" },
  });
  if (!result.ok()) throw new Error("Fixture unlock failed");
  await r.storageState({ path: "test-results/session.json" });
  await r.dispose();
}
