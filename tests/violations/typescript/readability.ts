// expect: max-params, max-depth, @typescript-eslint/no-magic-numbers, no-nested-ternary, eqeqeq, complexity, id-length, jsdoc/require-jsdoc
export function processOrder(a: number, b: number, c: number, d: number, e: number): number {
  if (a > 0) {
    if (b > 0) {
      if (c > 0) {
        if (d > 0) {
          return e * 86400;
        }
      }
    }
  }
  if (a == b) return 0;
  if (a > c && b > d) return 1;
  if (c > d || e > a) return -1;
  if (e > b) return 2;
  return a > 1 ? (b > 1 ? 1 : 0) : 0;
}
