//! Times what the CLI's defaults find in a file, per regex.
//!
//!     cargo run --release --example bench_file -- big.txt [--top N] [--json OUT]
//!
//! Prints the number of matches, the total time, and the slowest regexes. With `--json`,
//! it instead writes what `pywhat --json big.txt` prints to OUT, and the time that took.

use pywhat::{Filter, Identifier};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let path = args.first().expect("usage: bench_file FILE [--top N]");
    let top: usize = args
        .iter()
        .position(|a| a == "--top")
        .and_then(|i| args.get(i + 1))
        .and_then(|n| n.parse().ok())
        .unwrap_or(10);
    if let Some(out) = args
        .iter()
        .position(|a| a == "--json")
        .and_then(|i| args.get(i + 1))
    {
        let start = Instant::now();
        let identifier = Identifier::default().with_boundaryless_filter(Filter::default());
        let identified = identifier.identify_inputs(
            std::slice::from_ref(path),
            pywhat::InputOptions::default(),
            pywhat::Key::None,
            false,
        );
        let mut json = identified.to_json();
        json.push('\n');
        std::fs::write(out, &json).expect("writable");
        println!(
            "{} bytes of JSON in {:.3} s",
            json.len(),
            start.elapsed().as_secs_f64()
        );
        return;
    }
    let text = pywhat::unicode::decode(&std::fs::read(path).expect("readable file"));
    let start = Instant::now();
    pywhat::compile_all();
    let compile = start.elapsed();
    // The CLI's defaults: rarity 0.1:1, boundaryless for rarity 0.1:1
    let identifier = Identifier::default().with_boundaryless_filter(Filter::default());
    let start = Instant::now();
    let found = identifier.identify(&text);
    let total = start.elapsed();
    println!(
        "{} bytes, {} lines: {} matches in {:.3} s (compiling all regexes first: {:.3} s)",
        text.len(),
        text.lines().count(),
        found.len(),
        total.as_secs_f64(),
        compile.as_secs_f64()
    );
    // Per regex, sequentially
    let mut times = Vec::new();
    for entry in Filter::default().regexes() {
        let one = Identifier::default()
            .with_filter(
                Filter::new(Some(&[entry.name.as_str()]), &[], 0.0, 1.0).expect("its own name"),
            )
            .with_boundaryless_filter(Filter::default());
        let start = Instant::now();
        let matches = one.identify(&text).len();
        times.push((start.elapsed().as_secs_f64(), entry.name.as_str(), matches));
    }
    let sum: f64 = times.iter().map(|t| t.0).sum();
    times.sort_by(|a, b| b.0.total_cmp(&a.0));
    println!("sum of the regexes, one at a time: {sum:.3} s; slowest:");
    for (seconds, name, matches) in times.iter().take(top) {
        let engine = pywhat::engine_of(
            pywhat::regexes()
                .iter()
                .find(|e| e.name == *name)
                .expect("entry"),
            true,
        )
        .expect("compiles");
        println!("  {seconds:8.3} s  {matches:6} matches  {engine:?}  {name}");
    }
}
