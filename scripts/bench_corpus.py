"""
Write the benchmark text of docs/rust.md to target/bench.txt: the repository's README.md,
fixtures/file, pywhat/Data/regex.json and tests/*.py, with Unix line ends, 10 times over
(about 4 MB).

    python scripts/bench_corpus.py [--times 10]
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def corpus() -> str:
    files = [ROOT / "README.md", ROOT / "fixtures" / "file"]
    files += [ROOT / "pywhat" / "Data" / "regex.json"]
    files += sorted((ROOT / "tests").glob("*.py"))
    return "".join(
        path.read_text(encoding="utf-8").replace("\r\n", "\n") for path in files
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--times", type=int, default=10)
    args = parser.parse_args()
    text = corpus() * args.times
    out = ROOT / "target" / "bench.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"{out}: {len(text.encode())} bytes, {text.count(chr(10))} lines")


if __name__ == "__main__":
    main()
