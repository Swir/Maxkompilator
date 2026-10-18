using System;
using System.IO;

var resource = Path.Combine(AppContext.BaseDirectory, "Assets", "greeting.txt");
if (!File.Exists(resource))
{
    Console.Error.WriteLine("Missing bundled .NET resource.");
    return 10;
}
if (File.ReadAllText(resource).Trim() != "MAXKOMPILATOR_DOTNET_RESOURCE_OK")
{
    Console.Error.WriteLine("Bundled .NET resource has unexpected content.");
    return 11;
}
Console.WriteLine("MAXKOMPILATOR_DOTNET_RUNTIME_OK");
return 0;
