import { readFile } from "node:fs/promises";
import { analyzeArchitecture } from "../src/threatlens.mjs";

const input = JSON.parse(await readFile("data/sample-architecture.json", "utf8"));
const analysis = analyzeArchitecture(input);

console.log(JSON.stringify({
  architecture: analysis.architecture.name,
  risk: analysis.score,
  componentCount: analysis.architecture.components.length,
  threatCount: analysis.threats.length,
  topThreats: analysis.threats.slice(0, 5).map((item) => ({
    severity: item.severity,
    stride: item.stride,
    title: item.title,
    confidence: item.confidence
  }))
}, null, 2));
