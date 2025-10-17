/**
 * Test suite for data extraction module.
 * Mirrors Python test_extract.py (39 tests) for consistency.
 */
import "mocha";
import { expect } from "chai";
import {
  extractPhones,
  extractFacebook,
  extractLinkedin,
  extractTwitter,
  extractInstagram,
  extractAddress,
  extractAll,
} from "../src/extract";

// ---------- Phone Extraction Tests ----------

describe("extractPhones", () => {
  it("should extract US phone formats", () => {
    const html = "Call us at (212) 555-1234 or +1-415-555-6789";
    const phones = extractPhones(html);
    expect(phones).to.have.lengthOf(2);
    expect(phones).to.include("+12125551234");
    expect(phones).to.include("+14155556789");
  });

  it("should extract international formats", () => {
    const html = "UK: +44 20 1234 5678, Germany: +49 30 12345678";
    const phones = extractPhones(html);
    expect(phones).to.have.lengthOf(2);
    expect(phones.some(p => p.includes("44"))).to.be.true;
    expect(phones.some(p => p.includes("49"))).to.be.true;
  });

  it("should extract various formats", () => {
    const html = `
      <div>
        <p>Contact: 123-456-7890</p>
      </div>
      <div>
        <p>Or: (123) 456-7890</p>
      </div>
    `;
    const phones = extractPhones(html);
    // Both should normalize to same number
    expect(phones).to.have.lengthOf(1);
    expect(phones[0]).to.equal("+11234567890");
  });

  it("should deduplicate phone numbers", () => {
    const html = "(212) 555-1234 or call 212-555-1234 or +1-212-555-1234";
    const phones = extractPhones(html);
    expect(phones).to.have.lengthOf(1);
    expect(phones[0]).to.equal("+12125551234");
  });

  it("should ignore dates", () => {
    const html = "Event on 2024-01-15 or 2024/12/31";
    const phones = extractPhones(html);
    expect(phones).to.be.empty;
  });

  it("should ignore prices", () => {
    const html = "Price: $1,234.56 or €999.99";
    const phones = extractPhones(html);
    expect(phones).to.be.empty;
  });

  it("should handle empty input", () => {
    expect(extractPhones("")).to.be.empty;
    expect(extractPhones(null)).to.be.empty;
  });

  it("should extract from HTML with tags", () => {
    const html = `
      <div class="contact">
        <p>Phone: <strong>(555) 123-4567</strong></p>
        <span>Fax: 555-123-4568</span>
      </div>
    `;
    const phones = extractPhones(html);
    expect(phones).to.have.lengthOf(2);
  });
});

// ---------- Facebook Extraction Tests ----------

describe("extractFacebook", () => {
  it("should extract from href attributes", () => {
    const html = '<a href="https://www.facebook.com/company">Facebook</a>';
    const url = extractFacebook(html);
    expect(url).to.equal("https://facebook.com/company");
  });

  it("should normalize fb.com to facebook.com", () => {
    const html = '<a href="https://fb.com/page">FB</a>';
    const url = extractFacebook(html);
    expect(url).to.include("facebook.com");
  });

  it("should handle facebook.com without www", () => {
    const html = '<a href="http://facebook.com/page">Link</a>';
    const url = extractFacebook(html);
    expect(url).to.equal("https://facebook.com/page");
  });

  it("should return null when not found", () => {
    const html = "<p>No social media links here</p>";
    const url = extractFacebook(html);
    expect(url).to.be.null;
  });

  it("should handle empty input", () => {
    expect(extractFacebook("")).to.be.null;
    expect(extractFacebook(null)).to.be.null;
  });
});

// ---------- LinkedIn Extraction Tests ----------

describe("extractLinkedin", () => {
  it("should extract company LinkedIn", () => {
    const html = '<a href="https://www.linkedin.com/company/example-corp">LinkedIn</a>';
    const url = extractLinkedin(html);
    expect(url).to.include("linkedin.com/company/example-corp");
  });

  it("should extract personal LinkedIn", () => {
    const html = '<a href="https://linkedin.com/in/john-doe">Profile</a>';
    const url = extractLinkedin(html);
    expect(url).to.include("linkedin.com/in/john-doe");
  });

  it("should return null when not found", () => {
    const html = "<p>No LinkedIn here</p>";
    const url = extractLinkedin(html);
    expect(url).to.be.null;
  });

  it("should handle empty input", () => {
    expect(extractLinkedin("")).to.be.null;
    expect(extractLinkedin(null)).to.be.null;
  });
});

// ---------- Twitter Extraction Tests ----------

describe("extractTwitter", () => {
  it("should extract twitter.com URLs", () => {
    const html = '<a href="https://twitter.com/company">Twitter</a>';
    const url = extractTwitter(html);
    expect(url).to.include("twitter.com/company");
  });

  it("should extract x.com URLs", () => {
    const html = '<a href="https://x.com/company">X</a>';
    const url = extractTwitter(html);
    expect(url).to.include("x.com/company");
  });

  it("should return null when not found", () => {
    const html = "<p>No Twitter here</p>";
    const url = extractTwitter(html);
    expect(url).to.be.null;
  });

  it("should handle empty input", () => {
    expect(extractTwitter("")).to.be.null;
    expect(extractTwitter(null)).to.be.null;
  });
});

// ---------- Instagram Extraction Tests ----------

describe("extractInstagram", () => {
  it("should extract instagram.com URLs", () => {
    const html = '<a href="https://www.instagram.com/company">Instagram</a>';
    const url = extractInstagram(html);
    expect(url).to.include("instagram.com/company");
  });

  it("should handle instagram.com without www", () => {
    const html = '<a href="https://instagram.com/brand">IG</a>';
    const url = extractInstagram(html);
    expect(url).to.equal("https://instagram.com/brand");
  });

  it("should handle trailing slashes", () => {
    const html = '<a href="https://instagram.com/user/">Link</a>';
    const url = extractInstagram(html);
    expect(url).to.include("instagram.com/user");
  });

  it("should return null when not found", () => {
    const html = "<p>No Instagram here</p>";
    const url = extractInstagram(html);
    expect(url).to.be.null;
  });

  it("should handle empty input", () => {
    expect(extractInstagram("")).to.be.null;
    expect(extractInstagram(null)).to.be.null;
  });
});

// ---------- Address Extraction Tests ----------

describe("extractAddress", () => {
  it("should extract keyword-based addresses", () => {
    const html = "Visit us at: 123 Main Street, San Francisco";
    const address = extractAddress(html);
    expect(address).to.include("123 Main Street");
  });

  it("should extract structured addresses", () => {
    const html = "Located at 456 Oak Avenue, Suite 200, New York, NY 10001";
    const address = extractAddress(html);
    expect(address).to.include("456 Oak Avenue");
  });

  it("should extract addresses with suite numbers", () => {
    const html = "789 Pine Street, Suite 100, Boston, MA 02101";
    const address = extractAddress(html);
    expect(address).to.include("789 Pine");
    expect(address).to.include("Suite 100");
  });

  it("should extract headquarters addresses", () => {
    const html = "Headquarters: 321 Tech Drive, Austin, TX 78701";
    const address = extractAddress(html);
    expect(address).to.include("321 Tech Drive");
  });

  it("should extract from HTML with tags", () => {
    const html = `
      <div class="address">
        <p>Address: 111 Business Blvd, Seattle, WA 98101</p>
      </div>
    `;
    const address = extractAddress(html);
    expect(address).to.include("111 Business Blvd");
  });

  it("should return null when not found", () => {
    const html = "<p>No address information</p>";
    const address = extractAddress(html);
    expect(address).to.be.null;
  });

  it("should handle empty input", () => {
    expect(extractAddress("")).to.be.null;
    expect(extractAddress(null)).to.be.null;
  });
});

// ---------- extractAll Integration Tests ----------

describe("extractAll", () => {
  it("should extract complete data", () => {
    const html = `
      <div class="company-info">
        <a href="https://facebook.com/company">Facebook</a>
        <a href="https://linkedin.com/company/example">LinkedIn</a>
        <a href="https://twitter.com/example">Twitter</a>
        <a href="https://instagram.com/example">Instagram</a>
        <p>Call: (555) 123-4567</p>
        <p>Address: 123 Main St, San Francisco, CA 94105</p>
      </div>
    `;

    const result = extractAll(html);
    expect(result.phones).to.have.lengthOf(1);
    expect(result.phones[0]).to.include("555");
    expect(result.facebook_url).to.equal("https://facebook.com/company");
    expect(result.linkedin_url).to.include("linkedin.com/company/example");
    expect(result.twitter_url).to.include("twitter.com/example");
    expect(result.instagram_url).to.include("instagram.com/example");
    expect(result.address).to.include("123 Main St");
  });

  it("should extract partial data", () => {
    const html = `
      <div>
        <a href="https://facebook.com/page">FB</a>
        <p>Phone: (212) 555-0100</p>
      </div>
    `;

    const result = extractAll(html);
    expect(result.phones).to.have.lengthOf(1);
    expect(result.facebook_url).to.include("facebook.com");
    expect(result.linkedin_url).to.be.null;
    expect(result.twitter_url).to.be.null;
    expect(result.instagram_url).to.be.null;
    expect(result.address).to.be.null;
  });

  it("should handle no data", () => {
    const html = "<p>Just some random text</p>";
    const result = extractAll(html);
    expect(result.phones).to.be.empty;
    expect(result.facebook_url).to.be.null;
    expect(result.linkedin_url).to.be.null;
    expect(result.twitter_url).to.be.null;
    expect(result.instagram_url).to.be.null;
    expect(result.address).to.be.null;
  });

  it("should handle empty HTML", () => {
    const result = extractAll("");
    expect(result.phones).to.be.empty;
    expect(result.facebook_url).to.be.null;
  });

  it("should handle multiple phones", () => {
    const html = `
      Main: (555) 100-2000
      Support: (555) 100-2001
      Fax: (555) 100-2002
    `;
    const result = extractAll(html);
    expect(result.phones).to.have.lengthOf(3);
  });

  it("should maintain structure integrity", () => {
    const result = extractAll(null);
    expect(result).to.have.property("phones").that.is.an("array");
    expect(result).to.have.property("company_name");
    expect(result).to.have.property("facebook_url");
    expect(result).to.have.property("linkedin_url");
    expect(result).to.have.property("twitter_url");
    expect(result).to.have.property("instagram_url");
    expect(result).to.have.property("address");
  });
});
