const express = require("express");
const mongoose = require("mongoose");
const router = express.Router();

const todos = require("./todos");
// import other routes here
//   const users = require('./users');

router.get("/", (req, res) => {
  res.send("main page!");
});

// Sonda zdrowia: 200 gdy jest połączenie z MongoDB, 503 gdy nie ma
// (healthcheck w compose, readinessProbe w Kubernetesie)
router.get("/health", (req, res) => {
  const ok = mongoose.connection.readyState === 1;
  res.status(ok ? 200 : 503).send({ status: ok ? "ok" : "unavailable", db: ok ? "connected" : "disconnected" });
});

router.use("/todos", todos);
// use other routes here
// router.use('/users', users)

module.exports = router;
