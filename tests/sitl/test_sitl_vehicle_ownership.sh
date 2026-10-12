#!/usr/bin/env bash
# Regression coverage for per-invocation SITL Docker ownership.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture_dir="$(mktemp -d)"
fake_bin="${fixture_dir}/bin"
fake_state="${fixture_dir}/state"
fake_calls="${fixture_dir}/calls"
mkdir -p "${fake_bin}" "${fake_state}"
: >"${fake_calls}"

cleanup_fixture() {
  rm -rf "${fixture_dir}"
}
trap cleanup_fixture EXIT INT TERM

cat >"${fake_bin}/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

state="${FAKE_DOCKER_STATE:?}"
calls="${FAKE_DOCKER_CALLS:?}"
mode="${FAKE_DOCKER_MODE:-normal}"

next_id() {
  local lock="${state}/lock"
  while ! mkdir "${lock}" 2>/dev/null; do sleep 0.01; done
  local number=0
  [[ -r "${state}/counter" ]] && number="$(<"${state}/counter")"
  number=$((number + 1))
  printf '%s\n' "${number}" >"${state}/counter"
  rmdir "${lock}"
  printf '%064x\n' "${number}"
}

find_id_for_name() {
  local name="$1"
  local file
  for file in "${state}"/*.name; do
    [[ -e "${file}" ]] || continue
    [[ "$(<"${file}")" == "${name}" ]] || continue
    basename "${file}" .name
    return 0
  done
  return 1
}

case "${1:-}" in
  image)
    [[ "${2:-}" == inspect ]]
    if [[ "${mode}" == preflight-timeout ]]; then
      sleep 10
    fi
    exit 0
    ;;
  container)
    [[ "${2:-}" == inspect ]]
    shift 2
    format=""
    if [[ "${1:-}" == --format ]]; then
      format="$2"
      shift 2
    fi
    reference="${1:-}"
    printf 'inspect %s %s\n' "${format}" "${reference}" >>"${calls}"
    if [[ "${mode}" == unverified-owner && "${reference}" =~ ^[0-9a-f]{64}$ ]]; then
      printf '%064x\tforeign-token\n' 99
      exit 0
    fi
    if [[ -e "${state}/${reference}.name" ]]; then
      id="${reference}"
    elif id="$(find_id_for_name "${reference}")"; then
      :
    else
      echo "Error: No such object: ${reference}" >&2
      exit 1
    fi
    if [[ -n "${format}" ]]; then
      printf 'verified reference=%s id=%s token=%s\n' \
        "${reference}" "${id}" "$(<"${state}/${id}.token")" >>"${calls}"
      # Docker's Go formatter does not interpret backslash escapes in a
      # template, so {{.Id}}\\t{{...}} contains a literal backslash-t.
      printf '%s\\t%s\n' "${id}" "$(<"${state}/${id}.token")"
    fi
    exit 0
    ;;
  run)
    args=("$@")
    name=""
    cidfile=""
    token=""
    for ((index = 0; index < ${#args[@]}; index++)); do
      case "${args[index]}" in
        --name) name="${args[index + 1]}" ;;
        --cidfile) cidfile="${args[index + 1]}" ;;
        --label)
          [[ "${args[index + 1]}" == io.nidar.sitl.token=* ]] && token="${args[index + 1]#io.nidar.sitl.token=}"
          ;;
      esac
    done
    printf 'run name=%s cidfile=%s token=%s\n' "${name}" "${cidfile}" "${token}" >>"${calls}"
    if [[ "${mode}" == collision && "${name}" == *px4* ]]; then
      exit 125
    fi
    if [[ "${name}" == *client* ]]; then
      if [[ "${mode}" == failed-run || "${mode}" == collision ]]; then
        exit 125
      fi
      id="$(next_id)"
      printf '%s\n' "${name}" >"${state}/${id}.name"
      printf '%s\n' "${token}" >"${state}/${id}.token"
      [[ -n "${cidfile}" ]] && printf '%s\n' "${id}" >"${cidfile}"
      printf '%s\n' connection=connected component=companion-computer forwarding=off telemetry=ready
      if [[ "${mode}" == client-name-reuse ]]; then
        rm -f "${state}/${id}.name" "${state}/${id}.token"
        foreign="$(next_id)"
        printf '%s\n' "${name}" >"${state}/${foreign}.name"
        printf '%s\n' foreign-token >"${state}/${foreign}.token"
      elif [[ "${mode}" != persistent-client ]]; then
        rm -f "${state}/${id}.name" "${state}/${id}.token"
      else
        sleep 30
      fi
      exit 0
    fi
    id="$(next_id)"
    printf '%s\n' "${name}" >"${state}/${id}.name"
    printf '%s\n' "${token}" >"${state}/${id}.token"
    if [[ -n "${cidfile}" && "${mode}" != late-cidfile ]]; then
      printf '%s\n' "${id}" >"${cidfile}"
    fi
    if [[ "${mode}" == failed-run ]]; then
      exit 125
    fi
    sleep 30
    ;;
  rm)
    [[ "${2:-}" == -f ]]
    reference="${3:-}"
    printf 'rm %s\n' "${reference}" >>"${calls}"
    rm -f "${state}/${reference}.name" "${state}/${reference}.token"
    exit 0
    ;;
esac

echo "unexpected fake Docker invocation: $*" >&2
exit 99
SH
chmod +x "${fake_bin}/docker"

real_python3="$(command -v python3)"
cat >"${fake_bin}/python3" <<SH
#!/usr/bin/env bash
set -euo pipefail
if [[ "\${1:-}" == "-" && "\${2:-}" == 14540 ]]; then
  cat >/dev/null
  exit 0
fi
if [[ "\${FAKE_SIGNAL_DURING_LAUNCH:-false}" == true &&
      "\${1:-}" == *bounded-log.py ]] &&
   [[ ! -e "${fake_state}/signal-sent" ]]; then
  : >"${fake_state}/signal-sent"
  kill -TERM "\${PPID}"
fi
exec "${real_python3}" "\$@"
SH
chmod +x "${fake_bin}/python3"

run_sitl() {
  local mode="$1"
  local output="$2"
  local temporary_directory="${3:-${fixture_dir}/tmp-default}"
  local client_timeout=120
  [[ "${mode}" == persistent-client ]] && client_timeout=1
  mkdir -p "${temporary_directory}"
  set +e
  PATH="${fake_bin}:${PATH}" \
    TMPDIR="${temporary_directory}" \
    FAKE_DOCKER_STATE="${fake_state}" \
    FAKE_DOCKER_CALLS="${fake_calls}" \
    FAKE_DOCKER_MODE="${mode}" \
    NIDAR_CLIENT_BINARY="scripts/sitl-vehicle.sh" \
    NIDAR_SITL_TIMEOUT_SECONDS=2 \
    NIDAR_SITL_CLIENT_TIMEOUT_SECONDS="${client_timeout}" \
    NIDAR_SITL_CLEANUP_TIMEOUT_SECONDS=3 \
    NIDAR_SITL_DOCKER_TIMEOUT_SECONDS=1 \
    "${project_root}/scripts/sitl-vehicle.sh" >"${output}" 2>&1
  local status=$?
  set -e
  return "${status}"
}

assert_only_verified_ids_removed() {
  if grep -Eq '^rm (nidar-sitl-vehicle|$)' "${fake_calls}" ||
     grep -Ev '^rm [0-9a-f]{64}$|^(run|inspect|verified) ' "${fake_calls}" >/dev/null; then
    cat "${fake_calls}" >&2
    echo "cleanup used an unverified Docker name" >&2
    return 1
  fi
  local removed_id
  while read -r _ removed_id; do
    if ! grep -Eq "^verified reference=[^[:space:]]+ id=${removed_id} token=[0-9a-f]{32}$" "${fake_calls}"; then
      cat "${fake_calls}" >&2
      echo "cleanup removed an ID without a matching ownership verification" >&2
      return 1
    fi
  done < <(grep '^rm ' "${fake_calls}" || true)
}

# The fixed loopback endpoint is exclusive: concurrent launch attempts must
# serialize before Docker starts, rather than sharing PX4 telemetry or logs.
: >"${fake_calls}"
run_sitl normal "${fixture_dir}/one.log" "${fixture_dir}/tmp-one" & first_pid=$!
run_sitl normal "${fixture_dir}/two.log" "${fixture_dir}/tmp-two" & second_pid=$!
set +e
wait "${first_pid}"; first_status=$?
wait "${second_pid}"; second_status=$?
set -e
if ! { [[ ${first_status} -eq 0 && ${second_status} -ne 0 ]] ||
       [[ ${first_status} -ne 0 && ${second_status} -eq 0 ]]; }; then
  cat "${fixture_dir}/one.log" "${fixture_dir}/two.log" >&2
  echo "concurrent SITL launches were not serialized" >&2
  exit 1
fi
mapfile -t sim_names < <(sed -n 's/^run name=\([^ ]*\).*cidfile=.* token=.*/\1/p' "${fake_calls}" | grep -- '-px4-' | sort -u)
if [[ ${#sim_names[@]} -ne 1 ]]; then
  cat "${fake_calls}" >&2
  echo "the rejected concurrent launch reached Docker" >&2
  exit 1
fi
assert_only_verified_ids_removed

# A container created before cidfile publication is recovered by unique
# name-plus-token verification and is still removed by its immutable ID.
: >"${fake_calls}"
if ! run_sitl late-cidfile "${fixture_dir}/late-cidfile.log"; then
  cat "${fixture_dir}/late-cidfile.log" >&2
  echo "late cidfile recovery did not complete safely" >&2
  exit 1
fi
assert_only_verified_ids_removed

# A timed-out --rm client is still removed by its verified captured ID.
: >"${fake_calls}"
if run_sitl persistent-client "${fixture_dir}/persistent-client.log"; then
  cat "${fixture_dir}/persistent-client.log" >&2
  echo "expected persistent fake client to exceed its wallclock cap" >&2
  exit 1
fi
if [[ $(grep -c '^rm [0-9a-f]\{64\}$' "${fake_calls}") -lt 2 ]]; then
  cat "${fake_calls}" >&2
  echo "cleanup did not remove both owned client and simulator containers" >&2
  exit 1
fi
assert_only_verified_ids_removed

# A legacy-name collision must not trigger cleanup of a foreign container.
: >"${fake_calls}"
if run_sitl collision "${fixture_dir}/collision.log"; then
  cat "${fixture_dir}/collision.log" >&2
  echo "expected fake Docker name collision to fail" >&2
  exit 1
fi
assert_only_verified_ids_removed

# A failed Docker run must not cause name-based cleanup.
: >"${fake_calls}"
if run_sitl failed-run "${fixture_dir}/failed-run.log"; then
  cat "${fixture_dir}/failed-run.log" >&2
  echo "expected fake Docker run failure" >&2
  exit 1
fi
assert_only_verified_ids_removed

# Reusing a client name after its --rm exit must not remove the new owner.
: >"${fake_calls}"
run_sitl client-name-reuse "${fixture_dir}/reuse.log"
if grep -q '^rm .*client' "${fake_calls}"; then
  cat "${fake_calls}" >&2
  echo "cleanup removed a container after client-name reuse" >&2
  exit 1
fi
assert_only_verified_ids_removed

# A signal after cidfile creation still removes the exact owned simulator ID.
: >"${fake_calls}"
set +e
PATH="${fake_bin}:${PATH}" FAKE_DOCKER_STATE="${fake_state}" FAKE_DOCKER_CALLS="${fake_calls}" \
  FAKE_DOCKER_MODE=normal FAKE_SIGNAL_DURING_LAUNCH=true \
  NIDAR_CLIENT_BINARY="scripts/sitl-vehicle.sh" NIDAR_SITL_TIMEOUT_SECONDS=2 \
  NIDAR_SITL_CLEANUP_TIMEOUT_SECONDS=3 NIDAR_SITL_DOCKER_TIMEOUT_SECONDS=1 \
  "${project_root}/scripts/sitl-vehicle.sh" >"${fixture_dir}/signal.log" 2>&1
status=$?
set -e
if [[ ${status} -ne 143 ]]; then
  cat "${fixture_dir}/signal.log" >&2
  echo "signal during simulator launch did not preserve its exit status" >&2
  exit 1
fi
assert_only_verified_ids_removed

# If ID/token ownership verification is ambiguous, cleanup must fail closed.
: >"${fake_calls}"
if run_sitl unverified-owner "${fixture_dir}/unverified.log"; then
  cat "${fixture_dir}/unverified.log" >&2
  cat "${fake_calls}" >&2
  echo "unverified container ownership incorrectly succeeded" >&2
  exit 1
fi
if grep -q '^rm ' "${fake_calls}"; then
  cat "${fake_calls}" >&2
  echo "cleanup removed an unverified container" >&2
  exit 1
fi

# Docker preflight must be bounded and fail closed when the daemon stalls.
: >"${fake_calls}"
start_seconds=${SECONDS}
if run_sitl preflight-timeout "${fixture_dir}/timeout.log"; then
  cat "${fixture_dir}/timeout.log" >&2
  echo "unresponsive Docker preflight incorrectly succeeded" >&2
  exit 1
fi
if ((SECONDS - start_seconds > 3)) || ! grep -F 'required simulation is unavailable' "${fixture_dir}/timeout.log" >/dev/null; then
  cat "${fixture_dir}/timeout.log" >&2
  echo "Docker preflight did not fail closed within its configured bound" >&2
  exit 1
fi
