#!/usr/bin/env python3
import re
import subprocess
import sys


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


def main():
    # Test if we're in a git repo, to avoid `git diff` spamming the console
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"], encoding="utf-8"
        )
    except subprocess.CalledProcessError as e:
        exit(e.returncode)

    # Process arguments
    branch_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    diff_args = [a for a in sys.argv[1:] if a.startswith("-")]
    if len(branch_args) == 0:
        branch_args.append("develop")
    if len(branch_args) == 1:
        diff_args.insert(0, "--merge-base")

    # Generate a diff to know which lines have been touched
    diff = subprocess.check_output(
        [
            "git",
            "diff",
            "--unified=5",
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
        r"^\+[^\n]*((?:#|//|/\*)[ \t]*TODO[: \t][ \t]*[^\n]+)$",
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
    if not install_alias():
        main()
