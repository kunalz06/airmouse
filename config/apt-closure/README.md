# ARM64 runtime APT closure lock

This directory contains the committed, byte-sorted `dpkg-query` closure for
each stage of `docker/runtime/Dockerfile`. Its files are generated only by
`scripts/regenerate-runtime-apt-closure.sh` from an explicit, successful
bootstrap build against the pinned signed Ubuntu snapshot. The normal build
requires all three TSV files and fails if their exact installed closure differs.

The initial baseline cannot be fabricated in a network-isolated sandbox. Run
the regeneration command on an authorized Docker/buildx host, inspect the
resulting full closures, and add the generated `*.tsv` files plus
`config/apt-closure.lock.json` to the proposed change before enabling CI.
