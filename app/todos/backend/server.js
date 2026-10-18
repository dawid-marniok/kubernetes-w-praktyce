const express = require("express");
const cors = require("cors");
const mongoose = require("mongoose");
const routes = require("./routes");

// Cała konfiguracja przychodzi ze zmiennych środowiskowych (12-factor)
const PORT = process.env.PORT || 3001;
const MONGODB_URI = process.env.MONGODB_URI || "mongodb://mongo:27017/todos";
const RETRY_MS = 5000;

const app = express();
app.use(cors());
app.use(express.json());
app.use("/api", routes);

// Błędy z handlerów (Express 5 sam łapie odrzucone Promise)
app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).send({ error: err.message });
});

// Łączymy się z bazą w pętli: brak bazy przy starcie to nie powód, żeby kontener padł.
// Dopóki nie ma połączenia, /api/health zwraca 503.
async function connectWithRetry() {
  for (;;) {
    try {
      await mongoose.connect(MONGODB_URI, { serverSelectionTimeoutMS: 5000 });
      console.log("Połączono z MongoDB");
      return;
    } catch (err) {
      console.error(`Brak połączenia z MongoDB (${err.message}), ponawiam za ${RETRY_MS / 1000} s`);
      await new Promise((r) => setTimeout(r, RETRY_MS));
    }
  }
}

const server = app.listen(PORT, () => {
  console.log(`Server is listening on port: ${PORT}`);
});
connectWithRetry();

// Grzeczne zamknięcie po SIGTERM (docker stop, usunięcie poda)
process.on("SIGTERM", async () => {
  console.log("SIGTERM — zamykam serwer");
  server.close();
  await mongoose.disconnect();
  process.exit(0);
});
