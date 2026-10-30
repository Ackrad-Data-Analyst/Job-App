import { createHmac, timingSafeEqual, randomBytes } from "node:crypto";
export const COOKIE = "careerpilot_session";
function key() {
  const v = process.env.SESSION_SECRET;
  if (!v || v.length < 32)
    throw new Error("Start CareerPilot through its Start file.");
  return v;
}
export function sign() {
  const payload = Buffer.from(
    JSON.stringify({
      exp: Date.now() + 8 * 3600000,
      nonce: randomBytes(24).toString("base64url"),
    }),
  ).toString("base64url");
  return (
    payload +
    "." +
    createHmac("sha256", key()).update(payload).digest("base64url")
  );
}
export function valid(value?: string) {
  try {
    if (!value) return false;
    const [payload, sig] = value.split(".");
    const expected = createHmac("sha256", key()).update(payload).digest();
    const actual = Buffer.from(sig, "base64url");
    const data = JSON.parse(Buffer.from(payload, "base64url").toString());
    return (
      actual.length === expected.length &&
      timingSafeEqual(actual, expected) &&
      Number.isFinite(data.exp) &&
      data.exp > Date.now() &&
      data.exp < Date.now() + 9 * 3600000
    );
  } catch {
    return false;
  }
}
export function sameOrigin(request: Request) {
  const configured = process.env.APP_ORIGIN;
  return !!configured && request.headers.get("origin") === configured;
}
