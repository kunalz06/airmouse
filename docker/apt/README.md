# NIDAR Ubuntu snapshot trust bootstrap

`nidar-snapshot.sources` selects the exact Ubuntu snapshot
`20261001T000000Z` for Noble, Noble updates, security, and backports. Every
entry uses the Ubuntu archive keyring already carried by the digest-pinned
Ubuntu base image. APT release-signature verification remains enabled.

Ubuntu's minimal base does not contain `/etc/ssl/certs/ca-certificates.crt`.
Before the first HTTPS APT update, each stage copies the narrow bootstrap trust
bundle from `nidar-snapshot-ca-certificates.crt` to that path and verifies its
SHA-256:

```
22b557a27055b33606b6559f37703928d3e4ad79f110b407d04986e1843543d1
```

The bundle is the ISRG Root X1 certificate (subject `CN=ISRG Root X1`, valid
through 2035-06-04), taken byte-for-byte from Ubuntu Noble's
`ca-certificates` package version `20240203` at
`/usr/share/ca-certificates/mozilla/ISRG_Root_X1.crt`. It is deliberately
checked in, rather than downloaded during the build, so the initial TLS trust
anchor is reviewable and hash-pinned. The regular, snapshot-pinned
`ca-certificates` package is then installed normally.

Do not replace this with `--allow-unauthenticated`, insecure HTTPS options, or
a live mirror. If the snapshot server changes certificate chain, update this
bundle only with documented certificate provenance, a new SHA-256, review, and
a regenerated package closure.

`config/versions.lock` is the authoritative source for the snapshot URL,
suites, components, archive key path, bootstrap-bundle path and SHA-256,
closure-lock path, and closure schema. The offline policy checker derives its
expected Deb822 stanza and lock metadata from those fields and rejects an
installer whose hardcoded bootstrap checksum differs from the lock.

This applies only to `docker/runtime/Dockerfile`; development and simulation
Dockerfiles are unchanged. The first generated ARM64 closure contains 197
MAVSDK-build, 170 application-build, and 94 runtime packages. Its authorized
host bootstrap succeeded and a locked replay is running. It is not a completed
hosted-CI or independent-review gate.
