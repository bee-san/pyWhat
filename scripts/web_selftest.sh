#!/usr/bin/env bash
# Builds the WebAssembly page in web/ and checks, in headless Chrome, that it identifies the
# examples of the README (web/index.html?selftest). Needs wasm-bindgen 0.2.130, python3 and
# Chrome (CHROME, or google-chrome / chromium on the PATH).
set -euo pipefail
cd "$(dirname "$0")/.."
cargo rustc --lib --release --target wasm32-unknown-unknown --no-default-features \
    --features wasm --crate-type cdylib
rm -rf web/pkg
wasm-bindgen --target web --out-dir web/pkg target/wasm32-unknown-unknown/release/pywhat.wasm
chrome=${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser)}
port=${PORT:-8765}
python3 -m http.server --bind 127.0.0.1 --directory web "$port" >/dev/null 2>&1 &
server=$!
trap 'kill $server 2>/dev/null' EXIT
sleep 1
dom=$("$chrome" --headless=new --no-sandbox --disable-gpu --virtual-time-budget=20000 \
    --dump-dom "http://127.0.0.1:$port/index.html?selftest" 2>/dev/null)
status=$(grep -o '<p id="status">[^<]*' <<<"$dom" | sed 's/^<p id="status">//' || true)
echo "${status:-no SELFTEST status in the page}"
[[ $status == "SELFTEST OK"* ]]
