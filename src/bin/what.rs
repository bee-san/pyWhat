//! The `what` command: identify anything (see `what --help`).

fn main() {
    std::process::exit(pywhat::cli::main(std::env::args_os()))
}
