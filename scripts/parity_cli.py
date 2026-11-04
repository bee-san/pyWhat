"""
Check that the Rust CLI prints what the Python CLI prints: the same stdout and stderr bytes
and the same exit code, for about 290 command lines: every case of tests/test_click.py (read from
it), every option on fixtures/file, the examples of the README and of --help, and corner
cases of the argument parser, of stdin and of files. For --format pretty, whose table
comfy-table draws, the text around the table and the cells of the table must be the same.
Where Python stops with a traceback, its stderr isn't compared.

    cargo build --release
    python scripts/parity_cli.py [-k TEXT] [-v] [-j JOBS]

PYWHAT_CLI is the program to test (default: target/release/what). Python runs as
`COLUMNS=10000 python -m pywhat ...` from the root of the repository, so that rich doesn't
wrap its output, and the Rust CLI with the same environment and the program name "python -m
pywhat", so that the usage lines are the same.

Python lists the files of a directory in the order of the file system, and Rust in the order
of their names (#291, Python bug 5). So that the output for directories can be compared byte
for byte on any file system, Python runs with glob listing every directory in name order;
nothing else changes.

KNOWN lists the command lines whose output differs on purpose, with the reason. They run too,
and are reported, but they don't fail the check.
"""
import argparse
import ast
import itertools
import os
import re
import shlex
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
PROG = "python -m pywhat"

# python -m pywhat, with glob listing every directory in name order (see above)
PYTHON_CLI = """\
import glob
import runpy

files_of = glob._iterdir


def in_name_order(*args, **kwargs):
    yield from sorted(files_of(*args, **kwargs))


glob._iterdir = in_name_order
runpy.run_module("pywhat", run_name="__main__", alter_sys=True)
"""

ETH = "0x52908400098527886E0F7030069857D2E4169EE7"
F = "fixtures/file"
PNG = b"\x89PNG\r\n\x1a\nTHM{hello}\n"


class Case(NamedTuple):
    args: Tuple[str, ...]
    stdin: bytes = b""
    columns: str = "10000"
    # Run in a scratch directory with these files (name, contents)
    files: Optional[Tuple[Tuple[str, bytes], ...]] = None


def case(*args: str, stdin: bytes = b"", columns: str = "10000", files=None) -> Case:
    return Case(tuple(args), stdin, columns, None if files is None else tuple(files))


# The cases of tests/test_click.py


class Unsupported(Exception):
    """An expression of tests/test_click.py that value() can't work out."""


def value(node: Optional[ast.AST], names: Dict[str, Any]) -> Any:
    """
    The value of a simple expression of tests/test_click.py: literals, the names that
    parametrize or an assignment of a literal binds, lists and tuples with *starred items,
    dicts, and the sum of two lists. Raises Unsupported for anything else.
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        items: List[Any] = []
        for item in node.elts:
            if isinstance(item, ast.Starred):
                items.extend(value(item.value, names))
            else:
                items.append(value(item, names))
        return items if isinstance(node, ast.List) else tuple(items)
    if isinstance(node, ast.Dict):
        return {
            value(key, names): value(item, names)
            for key, item in zip(node.keys, node.values)
        }
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return value(node.left, names) + value(node.right, names)
    raise Unsupported(ast.dump(node) if node is not None else "None")


def parametrizations(function: ast.FunctionDef) -> Optional[List[Dict[str, Any]]]:
    """
    The parameters of every run of a test function (one run without parameters), or None
    if it is skipped.
    """
    runs: List[Dict[str, Any]] = [{}]
    for decorator in function.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        name = getattr(call.func if call else decorator, "attr", None)
        if name == "skip":
            return None
        if name != "parametrize" or call is None:
            continue
        names = [n.strip() for n in value(call.args[0], {}).split(",")]
        sets = []
        for values in value(call.args[1], {}):
            values = values if len(names) > 1 else [values]
            sets.append(dict(zip(names, values)))
        runs = [
            {**run, **parameters} for run, parameters in itertools.product(runs, sets)
        ]
    return runs


def invocations(function: ast.FunctionDef) -> Iterator[ast.Call]:
    """The calls of CliRunner.invoke() and run_cli_command() in a test function."""
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", None))
            if name in ("invoke", "run_cli_command"):
                yield node


def click_case(call: ast.Call, names: Dict[str, Any]) -> Case:
    """The command line of a call, with its input and its COLUMNS."""
    is_invoke = getattr(call.func, "attr", None) == "invoke"
    args = value(call.args[1] if is_invoke else call.args[0], names)
    if isinstance(args, str):
        args = shlex.split(args)
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    stdin = value(keywords["input"], names) if "input" in keywords else b""
    env = value(keywords["env"], names) if "env" in keywords else {}
    if set(env) - {"COLUMNS"} or not isinstance(stdin, (str, bytes)):
        raise Unsupported("environment or input")
    if isinstance(stdin, str):
        stdin = stdin.encode()
    return case(*args, stdin=stdin, columns=env.get("COLUMNS", "10000"))


def click_cases() -> List[Case]:
    """Every command line that tests/test_click.py runs, as far as value() works it out."""
    tree = ast.parse((ROOT / "tests" / "test_click.py").read_text(encoding="utf-8"))
    found: List[Case] = []
    for function in tree.body:
        if not isinstance(function, ast.FunctionDef):
            continue
        if not function.name.startswith("test_"):
            continue
        runs = parametrizations(function)
        if runs is None:
            continue
        # Names that the test binds to a literal, such as flag = "THM{...}"
        local: Dict[str, Any] = {}
        for node in ast.walk(function):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    try:
                        local[target.id] = value(node.value, {})
                    except Unsupported:
                        pass
        for call in invocations(function):
            for parameters in runs:
                try:
                    found.append(click_case(call, {**local, **parameters}))
                except Unsupported:
                    pass  # e.g. a file in tmp_path, or stdin that is a terminal
    return list(dict.fromkeys(found))


# Every option on fixtures/file
OPTIONS = [
    ["-r", "0:", F],
    ["--rarity", "0.5:", F],
    ["-r", ":0.5", F],
    ["-r", "0.2:0.8", F],
    ["-i", "Bug Bounty", F],
    ["-e", "Credentials,URL", F],
    ["-o", F],
    ["-k", "name", F],
    ["-k", "rarity", F],
    ["-k", "matched", F],
    ["-k", "likely", F],
    ["-k", "NONE", F],
    ["-k", "rarity", "--reverse", F],
    ["-k", "matched", "--reverse", "--json", F],
    ["--top", "10", F],
    ["--top", "5%", F],
    ["--top", "1.5 %", F],
    ["--top", "all", F],
    ["--top", "3", "-k", "name", F],
    ["--top", "3", "--json", F],
    ["-br", "0.6:", F],
    ["-bi", "URL", F],
    ["-be", "URL", F],
    ["-db", F],
    ["-dp", F],
    ["-db", "-dp", "--json", F],
    ["--map", "osm", F],
    ["--map", "GOOGLE", F],
    ["--json", "--map", "osm", "-dp", F],
    ["--json", F],
    ["-pt", F],
    ["-if", F],
    ["-if", "--json", F],
    ["--format", "pretty", F],
    ["--format", "pretty", "-pt", F],
    ["--format", "pretty", "--rarity", "0:", F],
    ["--format", "%m\t%n|%r|%t|%l", F],
    ["--format", "%d", F],
    ["--format", "%e", F],
    ["--format", "\\\\%m\\%n\\x", F],
    ["--stream", F],
    ["--stream", "-pt", F],
    ["--stream", "--json", F],
    ["--stream", "--format", "%m %n", F],
    ["--no-progress", "--json", F],
    ["--verify", "THM{no key}"],
    ["-o", "--format", "pretty", "fixtures"],
    ["--format", "pretty", "fixtures"],
]

# The examples of the README and of --help
README = [
    [ETH],
    ["dQw4w9WgXcQ"],
    ["--rarity", "0:", "dQw4w9WgXcQ"],
    ["https://youtu.be/dQw4w9WgXcQ"],
    ["youtube.com/watch?v=dQw4w9WgXcQ&t=42s"],
    ["--rarity", "0.2:0.8", "--include", "Identifiers,URL", "https://skerritt.blog"],
    [
        "--include",
        "Cryptocurrency Wallet",
        "--exclude",
        "Ripple Wallet",
        "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY",
    ],
    ["--include", "BTC Wallet,ETH Wallet", F],
    ["-k", "rarity", "--reverse", ETH],
    ["--top", "5%", ETH],
    ["--top", "1", ETH],
    ["-k", "likely", ETH],
    ["--json", ETH],
    ["--rarity", "0:", "--include", "UNIX Timestamp", "1637093119"],
    [
        "--rarity",
        "0:",
        "--include",
        "UNIX Timestamp",
        "--format",
        "%d",
        "1637093119.558717",
    ],
    ["3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F"],
    ["--disable-processing", "3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F"],
    ["--map", "osm", "52.6169586, -1.9779857"],
    ["--format", "pretty", "--map", "osm", "52.6169586, -1.9779857"],
    ["--include", "Bug Bounty", F],
    ["HTB{this is a flag}"],
    ["--", "52.6169586, -1.9779857"],
    ["--rarity", "0.6:", "myEmail@host.org"],
    [
        "--rarity",
        "0:",
        "--include",
        "credentials",
        "--exclude",
        "aws",
        "James:SecretPassword",
    ],
    ["-br", "0.6:", "-be", "URL", "123myEmail@host.org456"],
    ["--format", "%m - %n", "google.com htb{flag}"],
    ["--stream", "fixtures"],
    ["--format", "pretty", ETH],
]

# The argument parser, errors, help and the format string
PARSER = [
    ["-1606586780"],
    ["-h"],
    ["--nope", "THM{x}"],
    ["-ox", "THM{x}"],
    ["-kname", "-db", F],
    ["--top=1", ETH],
    ["--top", "=1", ETH],
    ["-r=0.5:", ETH],
    ["-br=0.5:", ETH],
    ["--json=1", ETH],
    ["--rarity"],
    ["-k"],
    ["-pt=", "x"],
    ["--map", "OSM", "52.6169586, -1.9779857"],
    ["--map", "o\u017fm", "52.6169586, -1.9779857"],
    ["--map", "bing", "x"],
    ["--map", "it's", "x"],
    ["--", "-db", "--", "THM{x}"],
    ["-"],
    ["-r", "--", "THM{x}"],
    ["--tags", "--version"],
    ["--names", "--tags"],
    ["--map", "x", "--tags"],
    ["--tags", "--map", "x"],
    ["--help", "--map", "x"],
    ["--map", "x", "--help"],
    ["-db", "--help"],
    ["--help"],
    ["--version"],
    ["-v", "THM{x}"],
    ["--rarity", "0.5", ETH],
    ["--rarity", "a:b", ETH],
    ["--rarity", "0.1:0.5:0.9", ETH],
    ["--rarity", ":", ETH],
    ["--rarity", " : ", ETH],
    ["--rarity", "1_0:", ETH],
    ["--rarity", "\u0660.\u0665:", ETH],
    ["--rarity", "nan:", ETH],
    ["--rarity", "-inf:inf", ETH],
    ["-br", "x:", ETH],
    ["-db", "-br", "x:", ETH],
    ["--key", "nope", ETH],
    ["--key", "rar\u0131ty", ETH],
    ["--top", "0", ETH],
    ["--top", "150%", ETH],
    ["--top", "abc", ETH],
    ["--top", " 2 ", ETH],
    ["--top", "99999999999999999999999999999", ETH],
    ["--top", "\x1c 5\x1f%\u3000", ETH],
    ["--top", "0" * 40 + "1", ETH],
    ["--include", "", ETH],
    ["--include", "btc wallet", "--exclude", "ETH WALLET", ETH],
    ["--stream", "--format", "pretty", "--json", "THM{x}"],
    ["--stream", "-k", "name", "--top", "1", "THM{x}"],
    ["-db"],
    ["--format", "None", "THM{x}"],
    ["--format", "", "THM{x}"],
    ["--format", "   ", "THM{x}"],
    ["--format", "%m\\", "THM{x}"],
    # Errors of click's parser have no usage line, invalid values have one
    ["-e"],
    ["--json=", ETH],
    ["-db=", "THM{x}"],
    ["--help", "--json=1"],
    ["--map"],
    # rich markup in the format string and in the data is rendered, as in Python, and
    # Python stops at a closing tag that closes nothing (rich's MarkupError)
    ["-db", "--format", "[/b]", "THM{x}"],
    ["-db", "--format", "[b]%m[/i]", "THM{x}", ETH],
    ["-db", "--format", "x[/]y %m", "THM{x}"],
    ["--stream", "-db", "--format", "[/b]%m", "THM{x}", ETH],
    ["-db", "--format", "[b]%m[/bold] [red bold]%n[/bold red]", "THM{y}"],
    ["-db", "--format", "[/b]", "nothing"],
    ["-db", "--format", "[b]%m[/b] [#ff0000]%n[/#ff0000]", "THM{y}"],
    ["-db", "--format", "\\[b]%m", "THM{y}"],
    ["-db", "--include", "Access-Control-Allow-Header", "Access-Control-Allow: *"],
]

# The matched text as rich markup and emoji codes (#291, Python bug 4)
BUG_4 = (
    "#291 Python bug 4: rich takes the matched text for markup and emoji codes "
    "(Rust prints it as it is)"
)
MARKUP = [
    ["-db", "thm{[bold]x[/bold]}"],
    ["-db", "THM{:smile:}"],
    ["-db", "--format", "%m", "THM{[i]x[/i]}"],
    ["-db", "--format", "pretty", "THM{[b]x[/b]}"],
    ["-db", "thm{[/x]}"],
]

OWN: List[Case] = [case(*args) for args in OPTIONS + README + PARSER + MARKUP]
OWN += [
    case("-db", "--format", ":smile: %m", "THM{y}"),
    # stdin, when there are no inputs
    case(stdin=b""),
    case("-db", stdin=b"fixtures/file\n"),
    case("--json", stdin="\ufeffTHM{bom}\r\n".encode("utf-16")),
    case("--json", stdin=b"\x00\x01" + "THM{wide}".encode("utf-16-le") + b"\xff\xfe"),
    case("-db", stdin=b"caf\xe9 THM{latin}"),
    # The help and the usage of errors at other widths
    case("--help", columns="40"),
    case("--help", columns="60"),
    case("--help", columns="79"),
    case("--help", columns="0"),
    case("--help", columns="abc"),
    case("--rarity", columns="40"),
    # Files in a scratch directory
    case(
        "-db",
        "image.png",
        "page.html",
        files=[("image.png", PNG), ("page.html", b"https://google.com\n")],
    ),
    case(
        "-db",
        "--json",
        "image.png",
        "page.html",
        files=[("image.png", PNG), ("page.html", b"https://google.com\n")],
    ),
    case("image.png", files=[("image.png", PNG)]),
    case("--stream", "image.png", files=[("image.png", PNG)]),
    case("--stream", "image.png", files=[("image.png", b"\x89PNG\r\n\x1a\n")]),
    case("--stream", "--format", "json", "image.png", files=[("image.png", PNG)]),
    case("--format", "pretty", "image.png", files=[("image.png", PNG)]),
    case(
        "--format", "pretty", "image.png", files=[("image.png", b"\x89PNG\r\n\x1a\n")]
    ),
    case("-db", "--json", "89504E470D0A1A0A", files=[("89504E470D0A1A0A", b"THM{x}")]),
    case(
        "--json",
        "utf16.txt",
        files=[("utf16.txt", "\ufeffTHM{x} bee@skerritt.blog\r\n".encode("utf-16"))],
    ),
    case("-if", "THM{name}.txt", files=[("THM{name}.txt", b"nothing")]),
    case("tabs.txt", "-pt", files=[("tabs.txt", b"x")]),
    case(
        "--format",
        "%m",
        "dir",
        files=[("dir/a\tb", b"THM{tab}"), ("dir/.hidden", b"THM{hidden}")],
    ),
    # A tab in a file name, in the File: line and in the table's File column
    case("-db", "tab\tname.txt", "THM{x}", files=[("tab\tname.txt", b"THM{t}")]),
    case(
        "--format",
        "pretty",
        "tab\tname.txt",
        "THM{x}",
        files=[("tab\tname.txt", b"THM{t}")],
    ),
    # Written out of name order, which is the order that some file systems list them in
    case(
        "--format",
        "%m",
        "dir",
        files=[
            ("dir/b.txt", b"THM{b}"),
            ("dir/c/a.txt", b"THM{c}"),
            ("dir/a", b"THM{a}"),
        ],
    ),
    case(
        "--json",
        "dir",
        "THM{text}",
        files=[("dir/b.txt", b"THM{b}"), ("dir/a.txt", b"THM{a}")],
    ),
]

# Command lines whose output differs on purpose
KNOWN: Dict[Tuple[str, ...], str] = {
    (): (
        "python -m pywhat without arguments prints the help (pywhat/__main__.py); the "
        "what and pywhat commands read stdin, in Python and in Rust"
    ),
    ("--version",): (
        "-v prints the version of the crate (6.0.0-alpha.1); Python's __version__ is "
        "5.0.0"
    ),
    ("-v", "THM{x}"): "the version (see --version)",
    ("-db", "--format", ":smile: %m", "THM{y}"): (
        "emoji codes in a --format string: rich prints :smile: as an emoji, Rust as it is"
    ),
}
KNOWN[("--format", "pretty", "tab\tname.txt", "THM{x}")] = (
    "a tab in the table: rich counts a tab as 0 columns wide when it sizes the column, "
    "then wraps the cell at the expanded tab; comfy-table shows the expanded tab"
)
for args in MARKUP:
    KNOWN[tuple(args)] = BUG_4
KNOWN[("-db", "thm{[/x]}")] = BUG_4 + "; Python crashes with a MarkupError"


def run(
    command: List[str], case: Case, cwd: Path, executable: Optional[str] = None
) -> Tuple[int, bytes, bytes]:
    env = dict(os.environ, COLUMNS=case.columns, PYTHONIOENCODING="utf-8")
    # python -m pywhat from a scratch directory too
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT), env.get("PYTHONPATH")])
    )
    env.pop("NO_COLOR", None)
    result = subprocess.run(
        command,
        executable=executable,
        input=case.stdin,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=600,
    )
    return result.returncode, result.stdout, result.stderr


def table_parts(output: str):
    """The text around the tables of the output, and the cells of the tables."""
    text: List[str] = []
    tables: List[List[List[str]]] = []
    row: List[List[str]] = []
    in_table = False
    for line in output.split("\n"):
        if line.startswith("┏"):
            in_table, row = True, []
            tables.append([])
            text.append("<table>")
        elif in_table and line[:1] in ("┡", "├", "└"):
            # The end of a row: its cells, the lines of each cell joined
            if row:
                cells = []
                for index in range(len(row[0])):
                    lines = [
                        parts[index] if index < len(parts) else "" for parts in row
                    ]
                    while lines and not lines[-1]:
                        lines.pop()
                    cells.append("\n".join(lines))
                tables[-1].append(cells)
            row = []
            in_table = line[:1] != "└"
        elif in_table:
            row.append([part.strip() for part in re.split("[┃│]", line)[1:-1]])
        else:
            text.append(line)
    return text, tables


def first_difference(a: str, b: str) -> str:
    index = next(
        (i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b))
    )
    start = max(0, index - 60)
    return (
        f"at {index}: Python {a[start:index + 60]!r}\n"
        f"      Rust   {b[start:index + 60]!r}"
    )


def compare(case: Case, what: str, verbose: bool) -> Tuple[str, str]:
    """("same" | "same cells" | "different", details) for a case."""
    with tempfile.TemporaryDirectory() as scratch:
        cwd = ROOT
        if case.files is not None:
            cwd = Path(scratch)
            for name, data in case.files:
                path = cwd / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        python = run([sys.executable, "-c", PYTHON_CLI, *case.args], case, cwd)
        rust = run([PROG, *case.args], case, cwd, executable=what)
    traceback = b"Traceback (most recent call last)" in python[2]
    same_stderr = traceback or python[2] == rust[2]
    if python[:2] == rust[:2] and same_stderr:
        return "same", ""
    details = []
    if python[0] != rust[0]:
        details.append(f"exit code: Python {python[0]}, Rust {rust[0]}")
    if not same_stderr:
        details.append(
            "stderr: "
            + first_difference(
                python[2].decode(errors="replace"), rust[2].decode(errors="replace")
            )
        )
    if python[1] != rust[1]:
        py_text = python[1].decode(errors="replace")
        rs_text = rust[1].decode(errors="replace")
        pretty = "pretty" in [arg.strip() for arg in case.args]
        if "--format" in case.args and pretty and python[0] == rust[0]:
            py_parts, rs_parts = table_parts(py_text), table_parts(rs_text)
            if py_parts == rs_parts and same_stderr:
                return "same cells", ""
            details.append("table: " + first_difference(repr(py_parts), repr(rs_parts)))
        else:
            details.append("stdout: " + first_difference(py_text, rs_text))
    if verbose:
        details.append(
            f"Python stderr: {python[2][-300:]!r}\nRust stderr: {rust[2][-300:]!r}"
        )
    return "different", "\n    ".join(details)


def program() -> str:
    """The program to test: $PYWHAT_CLI, as an absolute path (cases run elsewhere too)."""
    default = ROOT / "target" / "release" / ("what.exe" if os.name == "nt" else "what")
    return os.path.abspath(os.environ.get("PYWHAT_CLI") or default)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("-k", help="only the cases whose arguments contain this text")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-j", "--jobs", type=int, default=4)
    args = parser.parse_args()
    what = program()
    from_tests = click_cases()
    cases = list(dict.fromkeys(from_tests + OWN))
    if args.k:
        cases = [c for c in cases if any(args.k in arg for arg in c.args)]
    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda c: compare(c, what, args.verbose), cases))
    counts: Dict[str, int] = {}
    failures = 0
    for case_, (verdict, details) in zip(cases, results):
        known = KNOWN.get(case_.args)
        if verdict == "different" and known:
            verdict = "known difference"
        counts[verdict] = counts.get(verdict, 0) + 1
        if verdict == "different":
            failures += 1
            print(
                f"DIFFERENT {list(case_.args)} (COLUMNS={case_.columns})\n    {details}"
            )
        elif verdict == "known difference":
            print(f"KNOWN {list(case_.args)}: {known}")
        elif args.verbose:
            print(f"{verdict.upper()} {list(case_.args)}")
    summary = ", ".join(
        f"{count} {verdict}" for verdict, count in sorted(counts.items())
    )
    print(
        f"\n{len(cases)} command lines ({len(from_tests)} from tests/test_click.py): "
        f"{summary}"
    )
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
