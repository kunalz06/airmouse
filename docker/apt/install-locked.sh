#!/bin/sh
# Install one stage's exact APT closure from the pinned Ubuntu snapshot.
set -eu

stage=${1:?stage is required}
shift
mode=${NIDAR_APT_LOCK_MODE:-locked}
generation=${NIDAR_APT_BASELINE_GENERATION:-0}
lock_dir=/opt/nidar-apt-closure
lock_file=${lock_dir}/${stage}-packages.tsv
provenance_dir=/opt/nidar-provenance

case "${stage}" in
  mavsdk-build|app-build|runtime) ;;
  *) echo "unknown NIDAR APT stage: ${stage}" >&2; exit 64 ;;
esac
case "${mode}:${generation}" in
  locked:0)
    test -s "${lock_file}" || {
      echo "missing committed APT closure ${lock_file}; run scripts/regenerate-runtime-apt-closure.sh on an authorized host" >&2
      exit 65
    }
    # dpkg-query's package field may include a multiarch suffix. Versions and
    # package names must be non-empty, whitespace-free TSV fields.
    awk -F '\t' 'NF != 3 || $1 !~ /^[A-Za-z0-9+_.:-]+$/ || $2 !~ /^[^[:space:]]+$/ || $3 !~ /^(arm64|all)$/ { exit 1 } { print $1 "=" $2 }' "${lock_file}" > /tmp/nidar-apt-request
    test -s /tmp/nidar-apt-request || exit 65
    ;;
  bootstrap:1)
    # This is the deliberately explicit, one-time/reviewed lock regeneration
    # path. It still uses the dated signed snapshot and strict TLS/signature
    # checks, but no existing closure is available to compare yet.
    test "$#" -gt 0 || { echo "bootstrap requires requested packages" >&2; exit 64; }
    printf '%s\n' "$@" > /tmp/nidar-apt-request
    ;;
  *)
    echo "APT lock mode must be locked with generation=0, or bootstrap with generation=1" >&2
    exit 64
    ;;
esac

test "$(sha256sum /etc/ssl/certs/ca-certificates.crt | awk '{print $1}')" = \
  22b557a27055b33606b6559f37703928d3e4ad79f110b407d04986e1843543d1
test -r /usr/share/keyrings/ubuntu-archive-keyring.gpg
rm -f /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources
apt-get -o APT::Update::Error-Mode=any update
if [ "${mode}" = bootstrap ]; then
  # Bring base packages to versions represented by the dated snapshot before
  # recording the first full closure. This avoids locking hidden base-image
  # versions that are unavailable from that snapshot.
  DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y --no-install-recommends
fi
DEBIAN_FRONTEND=noninteractive xargs -r apt-get install -y --no-install-recommends < /tmp/nidar-apt-request
mkdir -p "${provenance_dir}"
LC_ALL=C dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' | LC_ALL=C sort > "${provenance_dir}/${stage}-packages.tsv"
test -s "${provenance_dir}/${stage}-packages.tsv"
if [ "${mode}" = locked ]; then
  cmp -s "${lock_file}" "${provenance_dir}/${stage}-packages.tsv" || {
    echo "installed APT closure differs from committed ${stage} lock" >&2
    exit 65
  }
fi
rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/nidar-apt-request
