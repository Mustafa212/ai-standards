// expect: S3776, S3358
namespace Demo.Violations
{
    /// <summary>Breaks RDB-1's cognitive complexity and RDB-7's nested conditionals on purpose.</summary>
    public static class Complexity
    {
        /// <summary>Nesting and broken flow push cognitive complexity past the limit.</summary>
        public static int Tangled(int first, int second, int limit)
        {
            var total = 0;
            for (var row = 0; row < first; row++)
            {
                if (row % 2 == 0)
                {
                    for (var col = 0; col < second; col++)
                    {
                        if (col > limit && (row > 1 || col < 5))
                        {
                            while (total < 100)
                            {
                                if (total % 3 == 0)
                                {
                                    total += 2;
                                }
                                else if (total % 5 == 0)
                                {
                                    total += 3;
                                }
                                else
                                {
                                    total += 1;
                                }
                            }
                        }
                    }
                }
            }

            return total;
        }

        /// <summary>A conditional inside a conditional.</summary>
        public static string Size(int count) => count > 10 ? "large" : count > 5 ? "medium" : "small";
    }
}
