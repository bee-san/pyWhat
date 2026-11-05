//! The `pywhat` command, the same as `what` (see `pywhat --help`).

fn main() {
    std::process::exit(pywhat::cli::main(std::env::args_os()))
}
