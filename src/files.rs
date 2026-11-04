//! Files, directories and several inputs: a port of `Identifier.iter_identify()`,
//! `Identifier._files()`, `Identifier._collect()` and `pywhat/magic_numbers.py`.

use crate::data::FILE_SIGNATURES_JSON;
use crate::identify::{check, to_identify_json, Identifier, Match};
use crate::ranking::{sort_matches, Key};
use crate::unicode;
use serde_json::{Map, Value};
use std::path::{Path, PathBuf, MAIN_SEPARATOR};
use std::sync::OnceLock;

/// The file signatures of `file_signatures.json`, in its order.
pub fn file_signatures() -> &'static [Map<String, Value>] {
    static SIGNATURES: OnceLock<Vec<Map<String, Value>>> = OnceLock::new();
    SIGNATURES.get_or_init(|| {
        serde_json::from_str(FILE_SIGNATURES_JSON).expect("file_signatures.json is valid")
    })
}

fn signature_hex(signature: &Map<String, Value>) -> &str {
    signature
        .get("Hexadecimal File Signature")
        .and_then(Value::as_str)
        .unwrap_or("")
}

/// `check_magic_nums()`: the file signature that the hexadecimal text starts with. A file
/// can only be one type, so it's the longest such signature (the first of them if several
/// are as long).
pub fn check_magic_numbers(hex: &str) -> Option<&'static Map<String, Value>> {
    let hex = hex.to_lowercase();
    let mut best: Option<&'static Map<String, Value>> = None;
    for signature in file_signatures() {
        let signature_hex = signature_hex(signature);
        if hex.starts_with(&signature_hex.to_lowercase())
            && best.is_none_or(|best| signature_hex.chars().count() > signature_hex_len(best))
        {
            best = Some(signature);
        }
    }
    best
}

fn signature_hex_len(signature: &Map<String, Value>) -> usize {
    signature_hex(signature).chars().count()
}

/// How many bytes of a file to read for its signature: as many as the longest signature.
fn header_size() -> usize {
    file_signatures()
        .iter()
        .map(signature_hex_len)
        .max()
        .unwrap_or(0)
        / 2
}

/// `get_magic_nums()`: the file signature of the bytes at the start of a file.
pub fn magic_numbers(data: &[u8]) -> Option<&'static Map<String, Value>> {
    let header = &data[..data.len().min(header_size())];
    let hex: String = header.iter().map(|b| format!("{b:02x}")).collect();
    check_magic_numbers(&hex)
}

/// What there is to search: a file (its location and path) or text.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Source {
    File { location: String, path: PathBuf },
    Text(String),
}

/// `os.path.abspath()`: an absolute path, `.` and `..` resolved without following links.
fn absolute(path: &Path) -> PathBuf {
    let joined = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir().unwrap_or_default().join(path)
    };
    let mut normal = PathBuf::new();
    for component in joined.components() {
        match component {
            std::path::Component::CurDir => {}
            std::path::Component::ParentDir => {
                if normal.parent().is_some() {
                    normal.pop();
                }
            }
            other => normal.push(other.as_os_str()),
        }
    }
    normal
}

/// `os.path.basename()`.
fn basename(path: &str) -> String {
    let separators: &[char] = if cfg!(windows) { &['/', '\\'] } else { &['/'] };
    path.rsplit(separators).next().unwrap_or(path).to_string()
}

/// The files of a directory, like `glob.iglob(glob.escape(dir) + "/**", recursive=True)`
/// keeps of them: every file, recursively, following links, without the files and
/// directories whose names start with `.`. Sorted by name in every directory (glob uses the
/// order of the file system).
fn directory_files(directory: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    let walker = walkdir::WalkDir::new(directory)
        .follow_links(true)
        .sort_by_file_name()
        .into_iter()
        .filter_entry(|entry| {
            entry.depth() == 0 || !entry.file_name().to_string_lossy().starts_with('.')
        });
    for entry in walker.flatten() {
        if entry.file_type().is_file() {
            files.push(entry.into_path());
        }
    }
    files
}

/// `Identifier._files()`: the files and texts to search in the inputs.
pub(crate) fn sources(inputs: &[String], only_text: bool) -> Vec<Source> {
    let several = inputs.len() != 1;
    let mut sources = Vec::new();
    for text in inputs {
        let path = Path::new(text);
        if !only_text && path.is_dir() {
            let directory = absolute(path);
            let directory_text = directory.to_string_lossy().into_owned();
            for file in directory_files(path) {
                let absolute_file = absolute(&file);
                let absolute_text = absolute_file.to_string_lossy().into_owned();
                // The path of the file in the directory, e.g. "/test/file"
                let mut location = absolute_text
                    .get(directory_text.len()..)
                    .unwrap_or("")
                    .to_string();
                if several {
                    // The directory joined with it, e.g. "fixtures/test/file"
                    let relative = location.trim_start_matches(MAIN_SEPARATOR);
                    location = join(text, relative);
                }
                sources.push(Source::File {
                    location,
                    path: absolute_file,
                });
            }
        } else if !only_text && path.is_file() {
            sources.push(Source::File {
                location: if several {
                    text.clone()
                } else {
                    basename(text)
                },
                path: path.to_path_buf(),
            });
        } else {
            sources.push(Source::Text(text.clone()));
        }
    }
    sources
}

/// `os.path.join(directory, relative)`.
fn join(directory: &str, relative: &str) -> String {
    if relative.is_empty() {
        return if directory.ends_with(MAIN_SEPARATOR) || directory.ends_with('/') {
            directory.to_string()
        } else {
            format!("{directory}{MAIN_SEPARATOR}")
        };
    }
    if directory.is_empty()
        || directory.ends_with(MAIN_SEPARATOR)
        || (cfg!(windows) && directory.ends_with('/'))
    {
        format!("{directory}{relative}")
    } else {
        format!("{directory}{MAIN_SEPARATOR}{relative}")
    }
}

/// Something that [`Identifier::iter_identify`] found.
#[derive(Debug, Clone)]
pub enum Found {
    /// The file signature of a file, found before the matches in the file.
    FileSignature {
        location: String,
        signature: &'static Map<String, Value>,
    },
    /// A match, in a file or in text (location "text").
    Match { location: String, found: Match },
}

/// Options for files and directories.
#[derive(Debug, Clone, Copy, Default)]
pub struct InputOptions {
    /// Search every input as text, even if it is the path of a file or a directory.
    pub only_text: bool,
    /// Search the names of the files too.
    pub include_filenames: bool,
}

/// What [`Identifier::identify_inputs`] found, like the dict that Python returns.
#[derive(Debug, Clone, Default)]
pub struct Identified {
    /// The file signatures, by location.
    pub signatures: Vec<(String, &'static Map<String, Value>)>,
    /// The matches of each location, in the order of their first match.
    pub regexes: Vec<(String, Vec<Match>)>,
}

impl Identified {
    /// The JSON of `--json`, byte for byte what `json.dumps()` of Python's result is.
    pub fn to_json(&self) -> String {
        let mut out = String::new();
        crate::identify::write_identify_json(
            &mut out,
            &self.regexes,
            Some(&self.signature_values()),
        );
        out
    }

    pub fn to_json_value(&self) -> Value {
        to_identify_json(&self.regexes, Some(&self.signature_values()))
    }

    fn signature_values(&self) -> Vec<(String, Value)> {
        self.signatures
            .iter()
            .map(|(location, signature)| (location.clone(), Value::Object((*signature).clone())))
            .collect()
    }

    /// Every match, with its location, in the order they were found.
    pub fn located_matches(&self) -> Vec<(String, Match)> {
        self.regexes
            .iter()
            .flat_map(|(location, matches)| {
                matches.iter().map(move |m| (location.clone(), m.clone()))
            })
            .collect()
    }

    /// Sorts the matches of every location (`identify(key=..., reverse=...)`).
    pub fn sort(&mut self, key: Key, reverse: bool) {
        for (_, matches) in &mut self.regexes {
            sort_matches(matches, key, reverse);
        }
    }

    /// Only the `top` most likely matches, most likely first (`top_matches()`): the location
    /// of the most likely match with its matches, then the location of the next most likely,
    /// and so on. `key` sorts the matches of each location instead.
    pub fn top(&self, top: &crate::ranking::Top, key: Key, reverse: bool) -> Identified {
        let found = crate::ranking::select(&self.located_matches(), top, 0, |(_, m)| m);
        Identified {
            signatures: self.signatures.clone(),
            regexes: group_by_location(found, key, reverse),
        }
    }

    fn add(&mut self, found: Found) {
        match found {
            Found::FileSignature {
                location,
                signature,
            } => {
                if let Some(existing) = self.signatures.iter_mut().find(|(l, _)| *l == location) {
                    existing.1 = signature;
                } else {
                    self.signatures.push((location, signature));
                }
            }
            Found::Match { location, found } => {
                if let Some((_, matches)) = self.regexes.iter_mut().find(|(l, _)| *l == location) {
                    matches.push(found);
                } else {
                    self.regexes.push((location, vec![found]));
                }
            }
        }
    }
}

/// `group_by_location()`.
fn group_by_location(
    found: Vec<(String, Match)>,
    key: Key,
    reverse: bool,
) -> Vec<(String, Vec<Match>)> {
    let mut regexes: Vec<(String, Vec<Match>)> = Vec::new();
    for (location, m) in found {
        if let Some((_, matches)) = regexes.iter_mut().find(|(l, _)| *l == location) {
            matches.push(m);
        } else {
            regexes.push((location, vec![m]));
        }
    }
    for (_, matches) in &mut regexes {
        sort_matches(matches, key, reverse);
    }
    regexes
}

/// The texts to search in a file, and its file signature.
type Contents = (Vec<String>, Option<&'static Map<String, Value>>);

/// The texts to search in a file, and its signature.
fn read_source(path: &Path, include_filenames: bool) -> std::io::Result<Contents> {
    let data = std::fs::read(path)?;
    let signature = magic_numbers(&data);
    let mut texts = unicode::texts(&data);
    if include_filenames {
        texts.push(basename(&path.to_string_lossy()));
    }
    Ok((texts, signature))
}

impl Identifier {
    /// Everything found in the inputs, file by file, as it is found (`iter_identify()`):
    /// for a file, its signature and then its matches. Calls `found` for each, and stops
    /// when `found` returns `false`. A file that can't be read is reported to `error`.
    pub fn iter_identify(
        &self,
        inputs: &[String],
        options: InputOptions,
        found: &mut dyn FnMut(Found) -> bool,
        error: &mut dyn FnMut(&str, std::io::Error),
    ) {
        let search = self.search();
        for source in sources(inputs, options.only_text) {
            let (location, texts) = match source {
                Source::Text(text) => ("text".to_string(), vec![text]),
                Source::File { location, path } => {
                    match read_source(&path, options.include_filenames) {
                        Ok((texts, signature)) => {
                            if let Some(signature) = signature {
                                if !found(Found::FileSignature {
                                    location: location.clone(),
                                    signature,
                                }) {
                                    return;
                                }
                            }
                            (location, texts)
                        }
                        Err(e) => {
                            error(&location, e);
                            continue;
                        }
                    }
                }
            };
            for text in &texts {
                let matches = match check(text, &search) {
                    Ok(matches) => matches,
                    Err(_) => self.identify(text),
                };
                for m in matches {
                    if !found(Found::Match {
                        location: location.clone(),
                        found: m,
                    }) {
                        return;
                    }
                }
            }
        }
    }

    /// Everything found in the inputs (`identify_inputs()`): files, directories (searched
    /// recursively) or text, sorted by `key`.
    pub fn identify_inputs(
        &self,
        inputs: &[String],
        options: InputOptions,
        key: Key,
        reverse: bool,
    ) -> Identified {
        let mut identified = Identified::default();
        self.iter_identify(
            inputs,
            options,
            &mut |found| {
                identified.add(found);
                true
            },
            &mut |_, _| {},
        );
        identified.sort(key, reverse);
        identified
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signatures() {
        let png = magic_numbers(b"\x89PNG\r\n\x1a\nrest").unwrap();
        assert_eq!(png["Filename Extension"], "png");
        // The longest signature: UTF-32LE's BOM starts with UTF-16LE's
        assert!(check_magic_numbers("fffe0000").unwrap()["Description"]
            .as_str()
            .unwrap()
            .contains("UTF-32"));
        assert!(check_magic_numbers("74686d7b").is_none());
        // Longer than 24 bytes (#296)
        assert_eq!(
            magic_numbers(b"SIMPLE  =                    T\n").unwrap()["Filename Extension"],
            "fits"
        );
    }

    #[test]
    fn join_like_os_path() {
        let sep = MAIN_SEPARATOR;
        assert_eq!(
            join("fixtures", "test/file"),
            format!("fixtures{sep}test/file")
        );
        assert_eq!(
            join(&format!("fixtures{sep}"), "file"),
            format!("fixtures{sep}file")
        );
    }
}
