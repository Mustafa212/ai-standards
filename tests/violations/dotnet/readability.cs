// expect: S107, S109, S134, S1541, S125, CS1591, IDE0161
namespace Demo.Violations
{
    public static class Readability
    {
        public static int ProcessOrder(int first, int second, int third, int fourth, int fifth)
        {
            if (first > 0)
            {
                if (second > 0)
                {
                    if (third > 0)
                    {
                        if (fourth > 0)
                        {
                            return fifth * 86400;
                        }
                    }
                }
            }
            // int previous = ProcessOrder(1, 2, 3, 4, 5);
            return 0;
        }

        public static bool IsSpecial(int code) =>
            code == 3 || code == 5 || code == 7 || code == 11 || code == 13 || code == 17
            || code == 19 || code == 23 || code == 29 || code == 31 || code == 37;
    }
}
