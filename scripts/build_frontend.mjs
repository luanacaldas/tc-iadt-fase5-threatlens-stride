import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, relative, resolve, sep } from "node:path";

const root = resolve(import.meta.dirname, "..");
const output = resolve(root, "dist");
if (relative(root, output).startsWith(`..${sep}`) || output === root) {
  throw new Error("Refusing to build outside the project workspace.");
}

if (existsSync(output)) rmSync(output, { recursive: true, force: true });
mkdirSync(join(output, "app"), { recursive: true });
mkdirSync(join(output, "data", "sample-diagrams"), { recursive: true });

const appFiles = ["index.html", "main.js", "runtime-config.js", "styles.css", "ui-contract.mjs"];
for (const file of appFiles) cpSync(join(root, "app", file), join(output, "app", file));
for (const file of readdirSync(join(root, "data", "sample-diagrams"))) {
  if (/\.(?:jpe?g|png|webp)$/i.test(file)) {
    cpSync(join(root, "data", "sample-diagrams", file), join(output, "data", "sample-diagrams", file));
  }
}

const builtFiles = [];
function inventory(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const absolute = join(directory, entry.name);
    if (entry.isDirectory()) inventory(absolute);
    else {
      const content = readFileSync(absolute);
      builtFiles.push({
        path: relative(output, absolute).replaceAll("\\", "/"),
        bytes: content.length,
        sha256: createHash("sha256").update(content).digest("hex"),
      });
    }
  }
}
inventory(output);
builtFiles.sort((left, right) => left.path.localeCompare(right.path));
const manifest = { schemaVersion: "1.0", version: "1.0.0-mvp", entrypoint: "app/index.html", files: builtFiles };
writeFileSync(join(output, "frontend-build-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Frontend production build created with ${builtFiles.length} files.`);
