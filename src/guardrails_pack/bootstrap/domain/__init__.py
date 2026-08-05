"""The pure rules of one projection: identity, substitution, and refusal.

Nothing here reads the filesystem, starts a process, or opens a socket. The
layer states what a valid project identity is, how the two pack tokens are
swapped, and what each refusal says. The application layer supplies the
external facts, and the adapters supply the effects.
"""
