# 3DGmax – notes for Claude

3D PMI viewer and comparison (Model Based Definition). Stack: Python 3.14 (pixi), PySide6, OCCT via pythonocc-core;
semantics, colors and graphical PMI from an own STEP reader. **Read `HANDOFF.md` and `PLAN.md` before any work.**
Sister project: ZGmax (`../Zeichnungsvergleich`).

## Rules
- The user writes German; answer in German. Do not invent library capabilities – verify by experiment.
- **Repository documents (README, PLAN, docs/, HANDOFF, CHANGELOG.md) and commit messages in English.**
- Code comments/docstrings German without umlauts (ae, oe, ue), short functions, no dead buttons.
- UI German by default (system language), all texts via `tr()`, English translation in `programm/i18n_en.json`
  (a test checks completeness: `pixi run python werkzeuge/tr_texte.py`).
- Every user-visible change goes into `programm/CHANGELOG.json` under `unreleased` (de and en, same order).
  **Bump versions only with `pixi run python packaging/release.py minor|patch|major --git`** (keeps CHANGELOG.md
  English and CHANGELOG_DE.md German, sets the tag); then `git push --follow-tags`.
- Keep `docs/Roadmap.md` (done/planned) up to date with every feature.
- Tests green before every commit, but **only the affected tests** (`pixi run test-betroffen`, maps the changed files
  to tests; on-screen: `DG_BILDSCHIRM=1 pixi run python -m pytest -q tests/test_bildschirm.py` when the 3D view
  changed). The full suite (`pixi run test`, ~25 min) only before a release, after changes to core modules (laden,
  p21, pmi_lesen, hauptfenster, ansicht3d) and in CI (PLAN §8.29). Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  **Push after every commit** (`origin` = github.com/maxwxyz/3DGmax, public).
- Scripts never touch the real user settings: set `DG_EINSTELLUNGEN=<tmp.ini>`.
- At the end of every answer update `HANDOFF.md` – **including a check against PLAN.md and docs/Roadmap.md**;
  unfinished work on a `wip/...` branch, not on `main`.
- After commit and push **delete branches that are no longer needed** (local and on GitHub).
- When no action is open: **pause and wait for the user's input**.
- Build: `packaging/build_*.sh|bat [--ohne-tests]`, GitHub workflow "Apps bauen".
