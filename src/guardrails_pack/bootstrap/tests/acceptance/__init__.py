"""The 53 acceptance assertions, run from the installed console script.

Three harness rules govern every module here.

* `H1` — every projection and every update runs from the console script of a
  throwaway tool installation of a freshly built wheel. A source checkout passes
  every packaging assertion even when the wheel is broken.
* `H2` — the checkout is committed before the wheel is built, because the
  payload is one archive of `HEAD`.
* `H3` — this suite is capability code. It is marked `acceptance`, the `tests`
  hook of the gate runs `-m "not acceptance"`, and the Root Pack runs the marked
  suite as its own CI job. Terminal Projection deletes this directory, so no
  Terminal Project ships an acceptance suite.
"""
