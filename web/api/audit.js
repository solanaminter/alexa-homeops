/** GET /api/audit -> hash-chained audit log entries. */
"use strict";

const { getAudit, verifyChain } = require("./_homeops");

module.exports = async (req, res) => {
  const { ok, checked } = verifyChain();
  res.setHeader("Content-Type", "application/json");
  res.status(200).json({
    status: "ok",
    chain_valid: ok,
    entries_checked: checked,
    entries: getAudit(25),
  });
};
