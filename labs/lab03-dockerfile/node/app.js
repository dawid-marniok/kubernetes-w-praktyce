const express = require('express');
const os = require('os');

const app = express();
const port = process.env.PORT || 3000;
const version = process.env.APP_VERSION || '1.0.0';

app.get('/', (req, res) => {
  res.send(`Hello z Node.js w kontenerze! Wersja ${version}, host ${os.hostname()}\n`);
});

// Endpoint do HEALTHCHECK (krok dla chętnych)
app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

// Kto uruchomił proces: uid 0 = root
app.get('/whoami', (req, res) => {
  const u = os.userInfo();
  res.json({ uid: u.uid, gid: u.gid, user: u.username });
});

const server = app.listen(port, () => {
  console.log(`Aplikacja słucha na porcie ${port}`);
});

// docker stop wysyła SIGTERM: zamykamy serwer od razu, bez czekania 10 s na SIGKILL
process.on('SIGTERM', () => {
  console.log('SIGTERM, zamykam');
  server.close(() => process.exit(0));
});
