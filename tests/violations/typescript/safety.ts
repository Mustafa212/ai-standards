// expect: @typescript-eslint/no-explicit-any, no-empty, @eslint-community/eslint-comments/require-description, @typescript-eslint/no-floating-promises, no-console
export function parse(input: any): void {
  try {
    JSON.parse(String(input));
  } catch {}
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  Promise.resolve(input);
  console.log(input);
}
