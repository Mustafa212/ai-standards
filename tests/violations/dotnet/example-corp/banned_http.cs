// expect: RS0030
namespace Demo.Violations;

/// <summary>Calls HTTP directly instead of through the org's client (EC-1).</summary>
public static class BannedHttp
{
    /// <summary>Creates a raw client.</summary>
    public static HttpClient Create() => new();
}
