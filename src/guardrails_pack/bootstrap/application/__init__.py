"""The ordered steps of the two operations the capability performs.

This layer owns the order of Terminal Projection and the order of the pipeline
that follows it. It reads and writes the filesystem, and it reaches every other
effect through the ports of `ports.py`, which the adapters implement. It imports
no adapter, because layers point inward.
"""
