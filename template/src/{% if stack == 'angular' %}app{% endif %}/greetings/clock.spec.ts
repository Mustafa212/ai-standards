import { Clock } from "./clock";

describe("Clock", () => {
  it("tells the current time", () => {
    const before = Date.now();

    expect(new Clock().now().getTime()).toBeGreaterThanOrEqual(before);
  });
});
