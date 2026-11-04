//! What a text *is*: `Identifier::identify_whole` against lemmeknow 0.8.0's `identify`,
//! which Ciphey calls on every candidate plaintext.
//!
//!     cargo bench --bench whole -- PLAINTEXT_DIR [--rounds 5] [--reps 20]
//!
//! PLAINTEXT_DIR holds Ciphey's plaintext-detection data (`benches/data/plaintext/*.tsv` of
//! bee-san/Ciphey: `category<TAB>split<TAB>text` lines). Every text is timed on its own:
//! `reps` calls in a row, divided by `reps`. The two libraries take turns, one round each,
//! and the median of each statistic over the rounds is printed. Both use rarity 0.1 to 1,
//! as Ciphey does.
//!
//! `--cold pywhat|pywhat-warm-up|lemmeknow` instead times the first call in this process,
//! which compiles the regexes (`pywhat-warm-up`: `Identifier::warm_up`, which compiles all
//! the regexes that the identifier uses, on rayon's thread pool).

use std::hint::black_box;
use std::time::Instant;

fn unescape(field: &str) -> String {
    let mut out = String::with_capacity(field.len());
    let mut chars = field.chars();
    while let Some(c) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some('t') => out.push('\t'),
            Some('n') => out.push('\n'),
            Some('r') => out.push('\r'),
            Some('\\') => out.push('\\'),
            Some(other) => {
                out.push('\\');
                out.push(other);
            }
            None => out.push('\\'),
        }
    }
    out
}

fn texts(dir: &str) -> Vec<String> {
    let mut paths: Vec<_> = std::fs::read_dir(dir)
        .expect("PLAINTEXT_DIR")
        .flatten()
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|e| e == "tsv"))
        .collect();
    paths.sort();
    let mut texts = Vec::new();
    for path in paths {
        let bytes = std::fs::read(&path).expect("readable");
        let text = String::from_utf8_lossy(&bytes);
        for line in text.lines() {
            let line = line.strip_suffix('\r').unwrap_or(line);
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let fields: Vec<&str> = line.split('\t').collect();
            if fields.len() == 3 {
                texts.push(unescape(fields[2]));
            }
        }
    }
    texts
}

fn percentile(sorted: &[f64], p: f64) -> f64 {
    let index = ((sorted.len() as f64 - 1.0) * p).round() as usize;
    sorted[index]
}

fn median(mut values: Vec<f64>) -> f64 {
    values.sort_by(f64::total_cmp);
    values[values.len() / 2]
}

fn main() {
    let args: Vec<String> = std::env::args()
        .skip(1)
        .filter(|a| a != "--bench")
        .collect();
    let option = |name: &str| {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .cloned()
    };
    if let Some(which) = option("--cold") {
        let start = Instant::now();
        match which.as_str() {
            "pywhat" => {
                black_box(pywhat::Identifier::default().identify_whole("https://example.com"));
            }
            "pywhat-warm-up" => pywhat::Identifier::default().warm_up(),
            "lemmeknow" => {
                black_box(
                    lemmeknow::Identifier::default()
                        .min_rarity(0.1)
                        .identify("https://example.com"),
                );
            }
            other => panic!("--cold {other}?"),
        }
        println!(
            "cold {which}: {:.1} ms",
            start.elapsed().as_secs_f64() * 1e3
        );
        return;
    }
    let dir = args
        .iter()
        .find(|a| !a.starts_with("--") && option("--rounds").as_deref() != Some(a.as_str()))
        .cloned()
        .or_else(|| std::env::var("PLAINTEXT_DIR").ok())
        .expect("usage: whole PLAINTEXT_DIR [--rounds N] [--reps N]");
    let rounds: usize = option("--rounds").and_then(|n| n.parse().ok()).unwrap_or(5);
    let reps: u32 = option("--reps").and_then(|n| n.parse().ok()).unwrap_or(20);
    let texts = texts(&dir);
    assert!(!texts.is_empty(), "no texts in {dir}");

    let pywhat = pywhat::Identifier::default();
    let lemmeknow = lemmeknow::Identifier::default().min_rarity(0.1);
    // Compile everything first
    pywhat::compile_all();
    for text in &texts {
        black_box(pywhat.identify_whole(text));
        black_box(lemmeknow.identify(text));
    }
    let (mut both, mut only_pywhat, mut only_lemmeknow) = (0, 0, 0);
    for text in &texts {
        match (
            !pywhat.identify_whole(text).is_empty(),
            !lemmeknow.identify(text).is_empty(),
        ) {
            (true, true) => both += 1,
            (true, false) => only_pywhat += 1,
            (false, true) => only_lemmeknow += 1,
            _ => {}
        }
    }
    println!(
        "{} texts from {dir}; identified by both: {both}, only pywhat: {only_pywhat}, only lemmeknow: {only_lemmeknow}",
        texts.len()
    );
    let mut stats: [Vec<[f64; 3]>; 2] = [Vec::new(), Vec::new()];
    for _ in 0..rounds {
        for (which, stat) in stats.iter_mut().enumerate() {
            let mut times: Vec<f64> = Vec::with_capacity(texts.len());
            for text in &texts {
                let start = Instant::now();
                for _ in 0..reps {
                    if which == 0 {
                        black_box(lemmeknow.identify(black_box(text)));
                    } else {
                        black_box(pywhat.identify_whole(black_box(text)));
                    }
                }
                times.push(start.elapsed().as_secs_f64() * 1e6 / f64::from(reps));
            }
            let mean = times.iter().sum::<f64>() / times.len() as f64;
            times.sort_by(f64::total_cmp);
            stat.push([percentile(&times, 0.5), percentile(&times, 0.99), mean]);
        }
    }
    for (which, name) in ["lemmeknow 0.8.0", "pywhat identify_whole"]
        .iter()
        .enumerate()
    {
        let column = |i: usize| median(stats[which].iter().map(|s| s[i]).collect());
        println!(
            "{name:22} p50 {:6.2} µs  p99 {:7.2} µs  mean {:6.2} µs  (median of {rounds} rounds, {reps} calls per text)",
            column(0),
            column(1),
            column(2)
        );
    }
}
