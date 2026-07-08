const fs = require("fs");
const path = require("path");
const { Client } = require("pg");

const TARGETS = [
  { file: "MarketData_XAUUSD_H1_2024-12-30.csv", table: "marketdata_xauusd_h1", year: 2024 },
  { file: "MarketData_XAUUSD_H1_2025-12-30.csv", table: "marketdata_xauusd_h1", year: 2025 },
  { file: "MarketData_XAUUSD_H1_2026-07-08.csv", table: "marketdata_xauusd_h1", year: 2026, cutoff: "2026.01.01 00:00:00" },
  { file: "MarketData_XAUUSD_H4_2020-12-30.csv", table: "marketdata_xauusd_h4", year: 2020 },
  { file: "MarketData_XAUUSD_H4_2021-12-29.csv", table: "marketdata_xauusd_h4", year: 2021 },
];

function loadEnv(file) {
  const env = {};
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const text = line.trim();
    if (!text || text.startsWith("#") || !text.includes("=")) continue;
    const i = text.indexOf("=");
    env[text.slice(0, i).trim()] = text.slice(i + 1).trim().replace(/^"|"$/g, "");
  }
  return env;
}

function fmtTime(value) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${value.getFullYear()}.${pad(value.getMonth() + 1)}.${pad(value.getDate())} ${pad(value.getHours())}:${pad(value.getMinutes())}:${pad(value.getSeconds())}`;
}

function fmtNum(value) {
  return Number(value).toFixed(2);
}

function dbRowToCsv(row) {
  return [
    fmtTime(row.time),
    fmtNum(row.open),
    fmtNum(row.high),
    fmtNum(row.low),
    fmtNum(row.close),
    row.volume,
    row.spread,
    fmtNum(row.ema200),
  ].join(",");
}

async function main() {
  const root = path.resolve(__dirname, "..", "..", "..");
  const csvDir = path.join(root, "Backtest_result");
  const env = loadEnv(path.join(root, "ValueCell_MT5", "backend", ".env"));
  const client = new Client({
    host: env.PGHOST,
    database: env.PGDATABASE,
    user: env.PGUSER,
    password: env.PGPASSWORD,
    port: Number(env.PGPORT || 5432),
    ssl: { rejectUnauthorized: false },
  });

  await client.connect();
  const summary = [];

  for (const target of TARGETS) {
    const csvPath = path.join(csvDir, target.file);
    const lines = fs.readFileSync(csvPath, "utf8").trimEnd().split(/\r?\n/);
    const header = lines[0];
    const originalRows = lines.slice(1);
    let keptRows = originalRows;

    if (target.cutoff) {
      keptRows = originalRows.filter((line) => line.split(",")[0] >= target.cutoff);
    }

    const csvTimes = new Set(keptRows.map((line) => line.split(",")[0]));
    const result = await client.query(`
      SELECT time, open, high, low, close, volume, spread, ema200
      FROM ${target.table}
      WHERE EXTRACT(YEAR FROM time)::int = $1
      ORDER BY time ASC
    `, [target.year]);

    const dbOnly = [];
    for (const row of result.rows) {
      const time = fmtTime(row.time);
      if (!csvTimes.has(time)) {
        dbOnly.push(dbRowToCsv(row));
      }
    }

    const merged = [header, ...keptRows, ...dbOnly];
    fs.writeFileSync(csvPath, `${merged.join("\n")}\n`, "utf8");
    summary.push({
      file: target.file,
      removed_before_cutoff: originalRows.length - keptRows.length,
      added_from_db: dbOnly.length,
      final_rows: keptRows.length + dbOnly.length,
      db_rows_for_year: result.rows.length,
    });
  }

  await client.end();
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({ name: error.name, code: error.code, message: error.message }));
  process.exit(1);
});
