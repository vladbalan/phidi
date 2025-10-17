import "mocha";
import { expect } from "chai";
import { canonicalDomain, maybeLogBrowserFallback, deriveCompanyName } from "../src/index";

describe("canonicalDomain", () => {
  const cases: Array<[string, string | null]> = [
    ["HTTPS://WWW.Example.com/Path?Q=1#frag", "example.com"],
    ["www.foo.io.", "foo.io"],
    ["bar.net/", "bar.net"],
    ["http://sub.domain.co.uk/page", "sub.domain.co.uk"],
    ["", null],
    ["   ", null],
  ];
  for (const [inp, out] of cases) {
    it(`canonicalizes '${inp}' -> '${out}'`, () => {
      expect(canonicalDomain(inp)).to.equal(out);
    });
  }
});

describe("deriveCompanyName", () => {
  it("derives 'Example' from 'example.com'", () => {
    expect(deriveCompanyName("example.com")).to.equal("Example");
  });

  it("derives 'My Company' from 'my-company.io'", () => {
    expect(deriveCompanyName("my-company.io")).to.equal("My Company");
  });

  it("derives 'Acme Corp' from 'acme-corp.net'", () => {
    expect(deriveCompanyName("acme-corp.net")).to.equal("Acme Corp");
  });

  it("handles domains with numbers", () => {
    expect(deriveCompanyName("abc123.com")).to.equal("Abc123");
  });
});

describe("maybeLogBrowserFallback", () => {
  it("logs a message for 'spa' domains", () => {
    let captured = "";
    const orig = console.log;
    try {
      console.log = (msg?: any) => {
        captured += String(msg ?? "");
      };
      maybeLogBrowserFallback("my-spa-app.com");
    } finally {
      console.log = orig;
    }
    expect(captured).to.contain("browser fallback");
  });
});
