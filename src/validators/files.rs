//! Validators (checksums) of the regexes in `pywhat/Data/regexes/files.json`, the same as
//! `pywhat/validators/files.py`: add a function, name it in [`validator`], and test that it
//! agrees with the Python one. Pure Rust only (the crate builds for wasm32).

/// The validator called `name`, if this area has one: add `("name", function)` to the table.
pub(super) fn validator(name: &str) -> Option<fn(&str) -> bool> {
    const VALIDATORS: super::Table = &[];
    VALIDATORS
        .iter()
        .find(|(validator, _)| *validator == name)
        .map(|(_, function)| *function)
}
