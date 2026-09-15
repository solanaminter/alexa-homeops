/** POST /api/chat {text} -> {reply, trace, approval}. Same contract as web/bridge.py. */
"use strict";

const { handleChat } = require("./_homeops");

function readBody(req) {
  return new Promise((resolve) => {
    if (req.body && typeof req.body === "object") return resolve(req.body);
    if (typeof req.body === "string") {
      try { return resolve(JSON.parse(req.body)); } catch { return resolve({}); }
    }
    let raw = "";
    req.on("data", (c) => { raw += c; });
    req.on("end", () => {
      try { resolve(raw ? JSON.parse(raw) : {}); }
      catch { resolve({}); }
    });
  });
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "method not allowed" });
    return;
  }
  const body = await readBody(req);
  const text = (body && typeof body.text === "string") ? body.text : "";
  res.setHeader("Content-Type", "application/json");
  res.status(200).json(handleChat(text));
};
