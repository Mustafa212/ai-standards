// expect: RS0030
namespace Demo.Violations;

/// <summary>Reads the machine clock instead of an injected TimeProvider (CS-24).</summary>
public static class WallClock
{
    /// <summary>The current moment, untestable.</summary>
    public static DateTimeOffset Now() => DateTimeOffset.UtcNow;
}
