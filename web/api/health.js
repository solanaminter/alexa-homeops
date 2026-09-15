/** GET /api/health -> backend info for the deployed demo. */
"use strict";

module.exports = async (req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.status(200).json({
    ok: true,
    backend: "vercel-serverless",
    note: "Simulated demo backend: scripted intent router over the bundled seed data " +
      "(web/data/household.json). The production backend is the self-hosted Python " +
      "MCP server + Strands agent — see the repo README.",
  });
};
