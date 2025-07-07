# git todo
A git subcommand to find all the TODOs that have been added/modified on your branch, while ignoring TODOs that exist elsewhere in the code.
Reviewing this list before merging may be a good idea, to make sure you haven't forgotten to make a change somewhere.

# Configuration
By default, the `git todo` command compares your current files against a main branch (typically you'd want this to be whatever your feature branch has diverged from and will be merged back into). It will guess a few common branch names (develop, main, master), or you can configure this using `git config`.

Supported configuration keys:
- `default-branch` The branch to compare against when you run `git todo` without any other arguments. Defaults to `develop`, `main`, or `master` if one of those exists.
- `context-lines` The number of context lines to search for additional comments following a TODO. Defaults to 5.

# License
This code is currently licensed under GPLv2, just like git. If you're already using git, this shouldn't be a problem.
