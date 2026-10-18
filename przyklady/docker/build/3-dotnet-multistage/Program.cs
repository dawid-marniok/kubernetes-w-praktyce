var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

// Zmień ten napis i zbuduj obraz ponownie — zobacz, które kroki idą z cache
app.MapGet("/", () => "Hello World from .NET!");

app.Run();
