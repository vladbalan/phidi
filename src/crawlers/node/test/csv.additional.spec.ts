import "mocha";
import { expect } from "chai";
import fs from "fs";
import path from "path";
import { loadDomains } from "../src/index";

function tmpFile(name: string): string {
  const dir = fs.mkdtempSync(path.join(fs.realpathSync(process.cwd()), "tmp-"));
  return path.join(dir, name);
}

describe("CSV loading - additional", () => {
  it("uses 'website' header when present", () => {
    const p = tmpFile("sites.csv");
    fs.writeFileSync(p, "website\nhttp://A.com\nWWW.B.org\n", "utf-8");
    expect(loadDomains(p)).to.deep.equal(["a.com", "b.org"]);
  });

  it("headerless single-column CSV", () => {
    const p = tmpFile("sites.csv");
    fs.writeFileSync(p, "example.com\nfoo.io\nbar.net\n", "utf-8");
    expect(loadDomains(p)).to.deep.equal(["example.com", "foo.io", "bar.net"]);
  });

  it("headerless delimited rows take first column", () => {
    const p = tmpFile("sites.csv");
    fs.writeFileSync(p, "example.com,extra\nwww.x.y/zzz,ignore\n", "utf-8");
    expect(loadDomains(p)).to.deep.equal(["example.com", "x.y"]);
  });

  it("dedupes while preserving order and ignores blanks", () => {
    const p = tmpFile("sites.csv");
    fs.writeFileSync(p, "domain\nexample.com\n\nfoo.io\nexample.com\n", "utf-8");
    expect(loadDomains(p)).to.deep.equal(["example.com", "foo.io"]);
  });
});
