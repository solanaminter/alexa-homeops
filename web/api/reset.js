/** POST /api/reset -> reseed demo state (scripted demo path only). */
"use strict";

const { reset } = require("./_homeops");

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "method not allowed" });
    return;
  }
  reset();
  res.setHeader("Content-Type", "application/json");
  res.status(200).json({ ok: true });
};
