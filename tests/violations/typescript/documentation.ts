// expect: jsdoc/require-jsdoc, sonarjs/cognitive-complexity
/** The class has its doc comment; its public method doesn't (RDB-8). */
export class Invoices {
  private readonly totals: number[] = [];

  add(total: number): void {
    this.totals.push(total);
  }
}

/** Nesting and broken flow push cognitive complexity past the limit (RDB-1). */
export function tangled(first: number, second: number, limit: number): number {
  let total = 0;
  for (let row = 0; row < first; row++) {
    if (row % 2 === 0) {
      for (let col = 0; col < second; col++) {
        if (col > limit && (row > 1 || col < 5)) {
          while (total < 100) {
            if (total % 3 === 0) {
              total += 2;
            } else if (total % 5 === 0) {
              total += 3;
            } else {
              total += 1;
            }
          }
        }
      }
    }
  }
  return total;
}
