const NOON_HOUR = 12;
const DEFAULT_NAME = "world";

/** Builds the greeting shown to the user: "Good morning" before noon, "Hello" after, and "world" for a blank name. */
export function buildGreeting(name: string, hour: number): string {
  const trimmedName = name.trim();
  const who = trimmedName === "" ? DEFAULT_NAME : trimmedName;
  const salutation = hour < NOON_HOUR ? "Good morning" : "Hello";
  return `${salutation}, ${who}!`;
}
