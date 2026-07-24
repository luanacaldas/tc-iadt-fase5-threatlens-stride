import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { join } from "node:path";

const root = process.cwd();
const python = process.env.PYTHON_EXECUTABLE || (
  process.platform === "win32"
    ? join(root, ".venv", "Scripts", "python.exe")
    : join(root, ".venv", "bin", "python")
);

if (!existsSync(python) && !process.env.PYTHON_EXECUTABLE) {
  console.error(`Python executable not found at ${python}`);
  process.exit(1);
}

const children = [
  spawn(
    python,
    ["-m", "uvicorn", "backend.main:app", "--host", process.env.BACKEND_HOST || "127.0.0.1", "--port", "8000"],
    { cwd: root, stdio: "inherit", windowsHide: true }
  ),
  spawn(process.execPath, ["server.mjs"], {
    cwd: root,
    stdio: "inherit",
    windowsHide: true
  })
];

let stopping = false;

function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  setTimeout(() => process.exit(exitCode), 250);
}

for (const child of children) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping && code !== 0) stop(code ?? 1);
  });
}

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

console.log("ThreatLens frontend: http://127.0.0.1:4173");
console.log("ThreatLens backend:  http://127.0.0.1:8000");
