//! False positives: how often each regex says that junk *is* something.
//!
//!     cargo bench --bench false_positives -- [--ciphey DIR] [--gib DIR] [--min-rarity 0.1]
//!         [--exclude-charset-only] [--show]
//!
//! Every text is identified with `Identifier::identify_whole` (what Ciphey asks: is this whole
//! text a known format?), with the default processors and rarity `--min-rarity` to 1 (0.1, as
//! Ciphey uses). A match on junk is a false positive. The corpora:
//!
//! - `--ciphey DIR`: Ciphey's plaintext-detection data (`benches/data/plaintext/` of
//!   bee-san/Ciphey). `captured.tsv` holds texts that Ciphey's search asked its checkers about
//!   which were not the answer (decoder output). `gutenberg.tsv` is English text, which isn't
//!   an identifier either.
//! - `--gib DIR`: gibberish-or-not's benchmark corpus v1 (`bench/corpus/v1/`): its `neg` samples
//!   (wrong Caesar, Vigenère, railfence ... keys, encodings, random bytes, mojibake), per split.
//! - Random strings: 9 alphabets (digits, hex, HEX, lower, upper, alphanumeric, Base64,
//!   Base64url, Base58) and every length from 1 to 200, 200 strings each, from a fixed seed.
//!
//! Prints the false positives of every regex that has any, per corpus, and the totals.
//! `--exclude-charset-only` leaves out the regexes tagged "Charset Only", as a checker that
//! asks "is this text a known format?" should; `--show` prints every match that isn't in the
//! random strings.

use std::collections::BTreeMap;

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
            Some('x') => {
                let hex: String = chars.by_ref().take(2).collect();
                match u32::from_str_radix(&hex, 16).ok().and_then(char::from_u32) {
                    Some(c) => out.push(c),
                    None => {
                        out.push_str("\\x");
                        out.push_str(&hex);
                    }
                }
            }
            Some('u') => {
                let hex: String = chars.by_ref().take(4).collect();
                match u32::from_str_radix(&hex, 16).ok().and_then(char::from_u32) {
                    Some(c) => out.push(c),
                    None => {
                        out.push_str("\\u");
                        out.push_str(&hex);
                    }
                }
            }
            Some(other) => {
                out.push('\\');
                out.push(other);
            }
            None => out.push('\\'),
        }
    }
    out
}

fn lines(path: &std::path::Path) -> Vec<Vec<String>> {
    let Ok(bytes) = std::fs::read(path) else {
        eprintln!("skipping {}: can't read it", path.display());
        return Vec::new();
    };
    String::from_utf8_lossy(&bytes)
        .lines()
        .map(|line| line.strip_suffix('\r').unwrap_or(line))
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(|line| line.split('\t').map(str::to_string).collect())
        .collect()
}

/// xorshift64*, like Ciphey's benches.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }
}

const ALPHABETS: [(&str, &str); 9] = [
    ("digits", "0123456789"),
    ("hex", "0123456789abcdef"),
    ("HEX", "0123456789ABCDEF"),
    ("lower", "abcdefghijklmnopqrstuvwxyz"),
    ("upper", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    (
        "alnum",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    ),
    (
        "base64",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
    ),
    (
        "base64url",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
    ),
    (
        "base58",
        "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
    ),
];

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
    let min_rarity: f64 = option("--min-rarity")
        .and_then(|r| r.parse().ok())
        .unwrap_or(0.1);
    // corpus name -> texts
    let mut corpora: BTreeMap<String, Vec<String>> = BTreeMap::new();
    // Ciphey's samples of formats that pyWhat should find (category -> texts)
    let mut positives: BTreeMap<String, Vec<String>> = BTreeMap::new();
    if let Some(dir) = option("--ciphey") {
        let dir = std::path::Path::new(&dir);
        for fields in lines(&dir.join("captured.tsv")) {
            if let Some(text) = fields.last() {
                corpora
                    .entry("ciphey captured (search candidates)".into())
                    .or_default()
                    .push(unescape(text));
            }
        }
        for fields in lines(&dir.join("curated.tsv")) {
            if let [category, _, text] = fields.as_slice() {
                if ["lemmeknow", "url", "email", "ip"].contains(&category.as_str()) {
                    positives
                        .entry(category.clone())
                        .or_default()
                        .push(unescape(text));
                }
            }
        }
        for fields in lines(&dir.join("gutenberg.tsv")) {
            if let Some(text) = fields.last() {
                corpora
                    .entry("ciphey gutenberg (English)".into())
                    .or_default()
                    .push(unescape(text));
            }
        }
    }
    if let Some(dir) = option("--gib") {
        for split in ["train", "dev", "test"] {
            let path = std::path::Path::new(&dir).join(format!("{split}.tsv"));
            for fields in lines(&path) {
                // id, lang, label, category, source, text
                if fields.len() >= 6 && fields[2] == "neg" {
                    corpora
                        .entry(format!("gib v1 {split} neg"))
                        .or_default()
                        .push(unescape(&fields[5]));
                }
            }
        }
    }
    let mut rng = Rng(0x1031_1104);
    for (name, alphabet) in ALPHABETS {
        let alphabet: Vec<char> = alphabet.chars().collect();
        let texts = corpora.entry(format!("random {name}")).or_default();
        for length in 1..=200 {
            for _ in 0..200 {
                texts.push(
                    (0..length)
                        .map(|_| alphabet[(rng.next() % alphabet.len() as u64) as usize])
                        .collect(),
                );
            }
        }
    }
    let exclude = args.iter().any(|a| a == "--exclude-charset-only");
    let mut identifier = pywhat::Identifier::default().min_rarity(min_rarity);
    if exclude {
        identifier = identifier.exclude_tags(&["Charset Only"]);
    }
    identifier.warm_up();
    let show = args.iter().any(|a| a == "--show");
    // regex name -> corpus -> false positives
    let mut by_regex: BTreeMap<String, BTreeMap<String, usize>> = BTreeMap::new();
    let mut totals: BTreeMap<String, (usize, usize)> = BTreeMap::new();
    for (corpus, texts) in &corpora {
        let mut texts_with_any = 0;
        for text in texts {
            let found = identifier.identify_whole(text);
            if !found.is_empty() {
                texts_with_any += 1;
            }
            for m in found {
                if show && !corpus.starts_with("random") {
                    println!("  {corpus}: {:?} is a {}", text, m.regex.name);
                }
                *by_regex
                    .entry(m.regex.name.clone())
                    .or_default()
                    .entry(corpus.clone())
                    .or_default() += 1;
            }
        }
        totals.insert(corpus.clone(), (texts_with_any, texts.len()));
    }
    println!(
        "False positives of identify_whole, rarity {min_rarity} to 1, default processors{}\n",
        if exclude {
            ", without \"Charset Only\""
        } else {
            ""
        }
    );
    println!("Texts with any match, per corpus:");
    for (corpus, (any, total)) in &totals {
        println!(
            "  {corpus:40} {any:6} of {total:7} ({:.3}%)",
            100.0 * *any as f64 / *total as f64
        );
    }
    if !positives.is_empty() {
        println!("\nCiphey's samples of formats (curated.tsv), identified:");
        for (category, texts) in &positives {
            let missed: Vec<&String> = texts
                .iter()
                .filter(|text| identifier.identify_whole(text).is_empty())
                .collect();
            println!(
                "  {category:40} {:6} of {:7}",
                texts.len() - missed.len(),
                texts.len()
            );
            if show {
                for text in missed {
                    println!("    not identified: {text:?}");
                }
            }
        }
    }
    println!("\nPer regex (total, then per corpus):");
    let mut rows: Vec<(usize, &String, &BTreeMap<String, usize>)> = by_regex
        .iter()
        .map(|(name, counts)| (counts.values().sum(), name, counts))
        .collect();
    rows.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(b.1)));
    for (total, name, counts) in rows {
        let detail: Vec<String> = counts.iter().map(|(c, n)| format!("{c}: {n}")).collect();
        println!("  {total:6}  {name}  [{}]", detail.join(", "));
    }
}
