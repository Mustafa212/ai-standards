import { buildGreeting } from "./greeting";

describe("buildGreeting", () => {
  it("says good morning before noon", () => {
    expect(buildGreeting("Mostafa", 9)).toBe("Good morning, Mostafa!");
  });

  it("says hello from noon on", () => {
    expect(buildGreeting("Mostafa", 15)).toBe("Hello, Mostafa!");
  });

  it("greets the world when the name is blank", () => {
    expect(buildGreeting("   ", 15)).toBe("Hello, world!");
  });
});
