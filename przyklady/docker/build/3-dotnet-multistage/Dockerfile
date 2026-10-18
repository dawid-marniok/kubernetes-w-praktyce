# ---- Etap 1: build (pełne SDK: kompilator, NuGet) ----
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Najpierw tylko plik projektu + restore: warstwa z pakietami NuGet
# idzie z cache, dopóki nie zmienisz zależności w .csproj
COPY *.csproj ./
RUN dotnet restore

# Potem reszta kodu i publikacja
COPY . .
RUN dotnet publish -c Release -o /app/publish --no-restore

# ---- Etap 2: runtime (sam ASP.NET Core, bez SDK) ----
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

# Obrazy .NET 8+ słuchają domyślnie na 8080 i mają użytkownika "app" (UID w $APP_UID)
USER $APP_UID
EXPOSE 8080

ENTRYPOINT ["dotnet", "sample.dll"]
