# Company facts — &lt;Company&gt;

Research artifact. Every concrete noun in the cover letter that names
this company (a product, customer, announcement, dollar figure, person)
MUST have a `## ` heading in this file, the fact itself, and the URL
where the fact was verified.

The heading slug is the anchor that `cover-letter.provenance.yaml`
cites as `source: company-fact:&lt;slug&gt;`. `scripts/check_provenance.py`
validates those anchors against this file.

## Research scope (spec §5.3 step 1)

The cover-letter-writer agent populates this file by fetching, in order:

1. The listing.json "about the company" blurb (if present).
2. `&lt;company-domain&gt;/` — homepage.
3. `&lt;company-domain&gt;/products`, `/customers`, `/solutions`.
4. Last six months of `&lt;company-domain&gt;/blog` or `/news`.
5. ATS page company blurb (Greenhouse/Lever/Ashby).

Anything not recorded here is not citeable in the letter.

---

## example-product-name

&lt;One-sentence statement of the fact.&gt;
&lt;https://example.com/product&gt;

## example-customer-name

&lt;E.g. "ACME is a publicly disclosed customer, cited in Company's Q3 case
study."&gt;
&lt;https://example.com/customers&gt;

## example-recent-announcement

&lt;E.g. "Company raised $X Series Z led by Investor, April 2026."&gt;
&lt;https://example.com/news/series-z&gt;

## example-founder-quote

&lt;Verbatim quote, attributed.&gt;
&lt;https://example.com/blog/founders-note&gt;
