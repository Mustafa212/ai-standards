// expect: IDE0040, IDE0065, IDE1006
namespace Demo.Violations;

using System.Text;

/// <summary>Breaks the CS-2 layout and naming rules on purpose.</summary>
public sealed class Style
{
    private readonly StringBuilder buffer = new();

    /// <summary>The text so far.</summary>
    string Text => buffer.ToString();

    /// <summary>Adds a line.</summary>
    public void Add(string line) => buffer.AppendLine(line).Append(Text.Length);
}
