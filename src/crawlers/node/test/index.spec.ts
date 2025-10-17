import "mocha"; // bring in describe/it types
import { expect } from "chai";
import fs from "fs";
import path from "path";

import {
  loadDomains,
  canonicalDomain,
  chunked,
  repoRoot,
} from "../src/index";

const root = repoRoot();

describe("CSV loading", () => {
  it("handles header variants and canonicalizes", () => {
    const tmp = fs.mkdtempSync(path.join(fs.realpathSync(process.cwd()), "tmp-"));
    const p = path.join(tmp, "sites.csv");
    fs.writeFileSync(p, "domain\nhttps://www.Example.com\nfoo.io\nbar.net/\n", "utf-8");
    const domains = loadDomains(p);
    expect(domains).to.deep.equal(["example.com", "foo.io", "bar.net"]);
  });

  it("handles BOM and delimiter sniff", () => {
    const tmp = fs.mkdtempSync(path.join(fs.realpathSync(process.cwd()), "tmp-"));
    const p = path.join(tmp, "sites.csv");
    // UTF-8 BOM + semicolon delimiter, with a header and two data rows
    const content = "\ufeffdomain;ignored\nwww.Foo.io;X\nhttp://bar.net;Y\n";
    fs.writeFileSync(p, content, "utf-8");
    const domains = loadDomains(p);
    expect(domains).to.deep.equal(["foo.io", "bar.net"]);
  });
});

describe("Orchestration", () => {
  it("batches with chunked", () => {
    const batches = chunked([0, 1, 2, 3, 4, 5, 6, 7], 3);
    expect(batches).to.deep.equal([[0, 1, 2], [3, 4, 5], [6, 7]]);
  });
});
