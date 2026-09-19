import { describe, expect, it } from "vitest";
import { tagSchema } from "./tag";

describe("tag form validation", () => {
  it("matches backend name and color bounds", () => {
    expect(tagSchema.safeParse({ name: "Work", color: "blue" }).success).toBe(true);
    expect(tagSchema.safeParse({ name: "", color: "blue" }).success).toBe(false);
    expect(tagSchema.safeParse({ name: "n".repeat(51) }).success).toBe(false);
    expect(tagSchema.safeParse({ name: "Work", color: "c".repeat(21) }).success).toBe(false);
  });
});
