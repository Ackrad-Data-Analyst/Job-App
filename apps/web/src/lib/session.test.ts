import { beforeEach, describe, expect, it, vi } from "vitest";
import { sign, valid, sameOrigin } from "./session";
beforeEach(() => {
  vi.useRealTimers();
  process.env.SESSION_SECRET =
    "fictional-session-test-only-00000000000000000000";
  process.env.APP_ORIGIN = "http://127.0.0.1:3100";
});
describe("private local sessions", () => {
  it("accepts a signed session and rejects a changed signature", () => {
    const token = sign();
    expect(valid(token)).toBe(true);
    const [p, s] = token.split(".");
    expect(valid(p + "." + (s[0] === "x" ? "y" : "x") + s.slice(1))).toBe(
      false,
    );
  });
  it("does not accept expired sessions", () => {
    vi.useFakeTimers();
    const token = sign();
    vi.advanceTimersByTime(9 * 3600000);
    expect(valid(token)).toBe(false);
  });
  it("rejects malformed data without throwing", () => {
    for (const v of ["", undefined, "a.b", "x", ".."])
      expect(valid(v)).toBe(false);
  });
  it("requires the exact configured mutation origin", () => {
    expect(
      sameOrigin(
        new Request("http://127.0.0.1:3100", {
          headers: { Origin: "http://127.0.0.1:3100" },
        }),
      ),
    ).toBe(true);
    expect(
      sameOrigin(
        new Request("http://127.0.0.1:3100", {
          headers: { Origin: "https://evil.example.invalid" },
        }),
      ),
    ).toBe(false);
  });
  it("rotating the key invalidates previous cookies", () => {
    const token = sign();
    process.env.SESSION_SECRET = "fictional-different-key-000000000000000000";
    expect(valid(token)).toBe(false);
  });
});
