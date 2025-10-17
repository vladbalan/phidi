import "mocha";
import { expect } from "chai";
import fs from "fs";
import path from "path";
import { run } from "../src/index";

function tmpDir(): string {
  return fs.mkdtempSync(path.join(fs.realpathSync(process.cwd()), "tmp-smoke-"));
}

describe("run() smoke", function () {
  this.timeout(10000);

  it("writes NDJSON via run() with temp files", async () => {
    const tmp = tmpDir();
    const input = path.join(tmp, "sites.csv");
    const output = path.join(tmp, "out.ndjson");

    fs.writeFileSync(input, ["domain", "example.com", "google.com", "github.com"].join("\n") + "\n", "utf-8");

    const code = await run({
      input,
      output,
      concurrency: 2,
      timeout: 5,
      userAgent: "Mozilla/5.0 (compatible; Test/1.0)",
    });

    expect(code).to.equal(0);
    expect(fs.existsSync(output)).to.equal(true);

    const lines = fs.readFileSync(output, "utf-8").trim().split(/\r?\n/);
    expect(lines.length).to.equal(3);

    const objs = lines.map((l) => JSON.parse(l));
    const domains = objs.map((o) => o.domain).sort();
    expect(domains).to.deep.equal(["example.com", "github.com", "google.com"].sort());
  });
});
