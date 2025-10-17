import "mocha";
import { expect } from "chai";
import fs from "fs";
import path from "path";
import { spawnSync, execSync } from "child_process";
import Ajv from "ajv";
import addFormats from "ajv-formats";
import { repoRoot } from "../src/index";

function ensureBuilt() {
  const distIndex = path.join(process.cwd(), "dist", "index.js");
  if (!fs.existsSync(distIndex)) {
    execSync("npm run build", { cwd: process.cwd(), stdio: "inherit" });
  }
}

function tmpDir(): string {
  const base = fs.mkdtempSync(path.join(fs.realpathSync(process.cwd()), "tmp-e2e-"));
  return base;
}

describe("CLI E2E", function () {
  this.timeout(15000);

  it("runs built binary and writes valid NDJSON", () => {
    ensureBuilt();

    const tmp = tmpDir();
    const input = path.join(tmp, "sites.csv");
    const output = path.join(tmp, "out.ndjson");

    // Prepare small input with real domains
    fs.writeFileSync(
      input,
      ["domain", "example.com", "google.com", "github.com"].join("\n") + "\n",
      "utf-8"
    );

    // Run built CLI using the current Node executable
    const cli = path.join(process.cwd(), "dist", "index.js");
    const args = [
      cli,
      "--input",
      input,
      "--output",
      output,
      "--concurrency",
      "2",
      "--timeout",
      "5",
      "--user-agent",
      "Mozilla/5.0 (compatible; Test/1.0)",
    ];

    const res = spawnSync(process.execPath, args, { encoding: "utf-8" });
    if (res.error) throw res.error;
    expect(res.status, res.stderr).to.equal(0);
    expect(res.stdout).to.contain("Node Crawler Starting");
    expect(res.stdout).to.contain("Batch 1/");
    expect(res.stdout).to.contain("Completed in");

    // Validate NDJSON
    expect(fs.existsSync(output)).to.equal(true);
    const lines = fs.readFileSync(output, "utf-8").trim().split(/\r?\n/);
    expect(lines.length).to.equal(3);

    const schemaPath = path.join(repoRoot(), "schemas", "crawl_result.schema.json");
    const schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));
    const ajv = new Ajv({ allErrors: true, strict: false });
    addFormats(ajv);
    const validate = ajv.compile(schema);

    const byDomain: Record<string, any> = {};
    for (const line of lines) {
      const obj = JSON.parse(line);
      expect(validate(obj), JSON.stringify(validate.errors)).to.equal(true);
      byDomain[obj.domain] = obj;
    }

    // Check that we got valid results with real HTTP data
    expect(byDomain["example.com"]).to.exist;
    expect(byDomain["example.com"].domain).to.equal("example.com");
    expect(byDomain["example.com"].http_status).to.be.a("number");
  });
});
