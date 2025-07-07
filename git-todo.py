#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess
import sys


COMMON_BRANCHES = [
    "develop",
    "main",
    "master",
]
DEFAULT_CONTEXT_LINES = 5


def install_alias():
    # Install a `git todo` alias that runs this script
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install":
            import shutil
            from pathlib import Path

            interpreter = Path(sys.executable).as_posix()
            try:
                if sys.platform == "win32":
                    # Prefer `py` launcher, if available
                    py = shutil.which("py")
                    if py:
                        subprocess.check_call(
                            [py, "--version"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        interpreter = Path(py).as_posix()
                else:
                    subprocess.check_call(
                        ["python3", "--version"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    interpreter = "python3"
            except:
                # Fallback to specifying current interpreter, even though this may break if Python is upgraded
                pass
            subprocess.check_call(
                [
                    "git",
                    "config",
                    "--global",
                    "alias.todo",
                    f"!{interpreter} {Path(__file__).as_posix()}",
                ]
            )
            print("Created alias: git todo")
            return True
        elif sys.argv[1] == "--uninstall":
            subprocess.check_call(
                ["git", "config", "--global", "--unset", "alias.todo"]
            )
            print("Removed alias: git todo")
            return True


def guess_main_branch():
    # Try to detect common branch names
    branches = subprocess.check_output(
        [
            "git",
            "branch",
            "--list",
            "--format=%(refname:lstrip=2)",
            "--",
            *COMMON_BRANCHES,
        ],
        encoding="utf-8",
    ).splitlines()
    # Prefer branches according to order defined above, not the (sorted) order git returns them in
    for b in COMMON_BRANCHES:
        if b and b in branches:
            print(f"Guessed main branch: {b}", file=sys.stderr)
            return b
    raise ValueError(
        "Unable to guess main branch! Specify as command line argument, or create config file .git-todo"
    )


def find_repo_root():
    # Find root of git repo
    return Path(
        subprocess.check_output(
            [
                "git",
                "rev-parse",
                "--show-toplevel",
            ],
            encoding="utf-8",
        ).removesuffix("\n")
    )


def get_config():
    config = DEFAULTS.copy()
    for entry in subprocess.check_output(
        [
            "git",
            "config",
            "--null",
            "--get-regexp",
            r"^todo\.",
        ],
        encoding="utf-8",
    ).split("\0"):
        if entry:
            key, _sep, value = entry.partition("\n")
            key = key.removeprefix("todo.")
            config[key] = value  # TODO: Do we have any need for multi-valued keys?
    return config


def main():
    try:
        git_repo_root = find_repo_root()
    except subprocess.CalledProcessError as e:
        # `git rev-parse` fails with a short error message to stderr if not inside a repo.
        # Much better than `git diff`, which spams it's full help text.
        exit(e.returncode)

    # Ask git for all config entries in the [todo] section
    try:
        config = get_config()
    except subprocess.CalledProcessError as e:
        exit(e.returncode)

    # Process arguments
    branch_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    diff_args = [a for a in sys.argv[1:] if a.startswith("-")]
    if len(branch_args) == 0:
        branch = config.get("default-branch") or guess_main_branch()
        branch_args.append(branch)
    if len(branch_args) == 1:
        diff_args.insert(0, "--merge-base")

    # Generate a diff to know which lines have been touched
    try:
        context_lines = int(config.get("context-lines") or "")
    except ValueError:
        context_lines = DEFAULT_CONTEXT_LINES
    diff = subprocess.check_output(
        [
            "git",
            "diff",
            f"--unified={context_lines}",
            "--diff-algorithm=histogram",
            "--no-color",
            "--no-prefix",
            "--no-relative",
            *diff_args,
            *branch_args,
        ],
        encoding="utf-8",
        universal_newlines=True,
    )

    # Slice diff into files
    FILE_HEADER_START = re.compile(r"^diff --git [^\n]+$", re.MULTILINE)
    FILE_HEADER_END = re.compile(r"^--- ([^\n]+)\n\+\+\+ ([^\n]+)$", re.MULTILINE)
    files: list[list[str]] = []
    pos = 0
    while (m_start := FILE_HEADER_START.search(diff, pos)) and (
        m_end := FILE_HEADER_END.search(diff, m_start.end())
    ):
        if len(files) > 0:
            files[-1][2] = diff[pos : m_start.start()]
        files.append([m_end.group(2), diff[m_start.start() : m_end.end()], None])
        pos = m_end.end()
    if len(files) > 0:
        if m_start:
            files[-1][2] = diff[pos : m_start.start()]
        else:
            files[-1][2] = diff[pos:]

    # Search for TODOs in files
    TODO = re.compile(
        r"^\+[^\n]*((?:#|//|/\*)[ \t]*TODO[: \t][ \t]*[^\n]+)$",  # TODO: Find TODO anywhere in comment, not just at the beginning. We may want to trim text that appears before the TODO though... How to display that cleanly? Maybe use comment char and ellipsis:   # ... TODO: figure this out
        re.MULTILINE | re.IGNORECASE,
    )
    COMMENT = re.compile(
        r"^[ \+][ \t]*((?:#|//|/\*)[^\n]+)$",
        re.MULTILINE | re.IGNORECASE,
    )
    HUNK_HEADER = re.compile(
        r"^@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@[^\n]*$", re.MULTILINE
    )
    for [file_name, file_header, file_diff] in files:  # TODO: Use comment syntax based on file type
        # Skip files without any TODOs
        if TODO.search(file_diff):
            # Parse the diff to know where the TODOs are
            new_line = 0
            count = 0
            indent = 0
            for line in file_diff.splitlines():
                if m := HUNK_HEADER.match(line):
                    new_line = int(m.group(3))
                    count = 0
                elif line:
                    # Print TODOs and aligned comments that directly follow them (until end of context lines)
                    if m := TODO.search(line):
                        if count == 0:
                            print(f"at {file_name}:{new_line}")
                        print(f"    {m[1]}")
                        count = 1
                        indent = m.start(1)
                    elif count > 0 and line[0] != "-":
                        if (
                            (m := COMMENT.search(line))
                            and m.start(1) == indent
                            and m.group(1).lstrip("#/ \t")
                        ):
                            print(f"    {m[1]}")
                            count += 1
                        else:
                            count = 0
                    # Track line numbers in new version of file
                    if line[0] in " +":
                        new_line += 1


if __name__ == "__main__":
    if not install_alias():  # TODO: Adding a version number (and --version command) might be a good idea. Maybe an update mechanism too, if we're comfortable pointing at GitHub?
        main()
