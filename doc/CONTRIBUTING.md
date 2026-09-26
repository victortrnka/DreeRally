# Contribution Guide

**Working on your first Pull Request?** You can learn how from this *free* series [How to Contribute to an Open Source Project on GitHub](https://egghead.io/series/how-to-contribute-to-an-open-source-project-on-github)

This guide outlines useful resources, tools and processes for contribution to
DreeRally.

## Goal

DreeRally is a *readable decompilation*: every function stays 1:1 with the
original `dr.exe`, but with real names, types and structs instead of Hex-Rays
artifacts (`sub_*`, `dword_*`, `*(_DWORD *)(a1 + 12)`).

## Naming

* Functions get plain camelCase names: `sub_40D920` -> `drawCarInRace`.
  Do not append the address to the name any more.
* Keep the `//----- (0040D920) -----` marker above every function. It links the
  function to the original binary, and the Ghidra tools read it.
* Globals: `dword_4A7DBC` -> `carSpeed`, with the original address in a comment
  at the definition (`// 0x4A7DBC`).
* Existing names with an address suffix (`drawCarInRace_40D920`) are renamed
  gradually, as ordinary refactor commits.
* Identifiers and comments are in English. Translate Spanish comments when you
  touch them.

## Commits

* Prefix the subject with `refactor:`, `fix:`, `build:` or `docs:`.
* Keep subjects short (at most 50 characters).
* A `refactor:` commit must pass `make check-equiv` (see `doc/DEVELOPMENT.md`).
* A `fix:` commit explains what changes and why it matches the original
  (function address and evidence), and ends with the trailers
  `Original: 0x<addr> <name>` and `Checked: <evidence>` as its last paragraph.
* Never mix refactoring and behaviour changes in one commit.

## Branches

The project have a few braches:

* master: this is the release branch. When a release is generated changes will be in the mater branch.
* dev-branches: this branches will be called like 0.1.x, and will contain the developments for this release.
