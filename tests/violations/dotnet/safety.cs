// expect: CA1031, CA1507, CA1852, CA2016, IDE0008
namespace Demo.Violations;

/// <summary>Breaks the CS safety rules on purpose.</summary>
public static class Safety
{
    /// <summary>Swallows every exception (CS-4) and hides a non-obvious type behind var (CS-3).</summary>
    public static int ParseOrZero(string text)
    {
        try
        {
            var value = int.Parse(text, System.Globalization.CultureInfo.InvariantCulture);
            return value;
        }
        catch (Exception)
        {
            return 0;
        }
    }

    /// <summary>Names a parameter with a string literal (CS-7).</summary>
    public static string Require(string? text) => text ?? throw new ArgumentNullException("text");

    /// <summary>Drops the cancellation token (CS-5).</summary>
    public static async Task WaitAsync(CancellationToken cancellationToken) =>
        await Task.Delay(TimeSpan.FromMilliseconds(1));
}

/// <summary>Not sealed although nothing derives from it (CS-6).</summary>
internal class Unsealed
{
    /// <summary>Any value.</summary>
    public int Value { get; init; }
}
