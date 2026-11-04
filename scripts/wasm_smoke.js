// Checks the WebAssembly build under Node.js:
//   cargo rustc --lib --release --target wasm32-unknown-unknown --no-default-features --features wasm --crate-type cdylib
//   wasm-bindgen --target nodejs --out-dir target/wasm-node target/wasm32-unknown-unknown/release/pywhat.wasm
//   node scripts/wasm_smoke.js target/wasm-node/pywhat.js
const assert = require("node:assert");
const pywhat = require(require("node:path").resolve(process.argv[2] || "target/wasm-node/pywhat.js"));

const names = (json) =>
  Object.values(JSON.parse(json).Regexes || {}).flat().map((m) => m["Regex Pattern"].Name);

// Anchored (the default here): the whole line must be the match
assert.deepStrictEqual(names(pywhat.identify("thm{flag}", "")), ["TryHackMe Flag Format"]);
assert.deepStrictEqual(names(pywhat.identify("a thm{flag} b", "{}")), []);
// Boundaryless, like the CLI
const found = names(pywhat.identify("a thm{flag} b bee@skerritt.blog", '{"boundaryless": true}'));
assert.ok(found.includes("TryHackMe Flag Format"), found);
assert.ok(found.includes("Email Address"), found);
// The JSON is what pywhat --json prints
const json = pywhat.identify("192.168.0.1", '{"boundaryless": true}');
assert.ok(json.startsWith('{"File Signatures": null, "Regexes": {"text": [{"Matched": "192.168.0.1"'), json);
// Filters, processors and errors
// Tags and names are case-insensitive: "Unix Timestamp" is also the tag "UNIX Timestamp" of both
assert.deepStrictEqual(names(pywhat.identify("1637093119", '{"min_rarity": 0, "include": ["UNIX Timestamp"]}')), ["Recent Unix Timestamp", "Unix Timestamp"]);
assert.ok(JSON.parse(pywhat.identify("1637093119", '{"min_rarity": 0, "include": ["Unix Timestamp"]}')).Regexes.text[0]["Regex Pattern"].Description.includes("November 16, 2021"));
assert.ok(JSON.parse(pywhat.identify("x", '{"include": ["no such tag"]}')).error);
assert.ok(JSON.parse(pywhat.tags()).includes("Bug Bounty"));
assert.ok(pywhat.version().startsWith("6."));
console.log("wasm smoke test: OK (" + pywhat.version() + ")");
