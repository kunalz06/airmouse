# Phase 4A MAVSDK ARM64 packaging selection

Verification date: 2026-10-06

## Selected path

Build MAVSDK **v3.17.2** from its exact upstream source commit
`9e3ca17faa84aa868caea10a3bbdab7e53810ced` inside the `linux/arm64`
runtime builder stage. The source is cloned from
<https://github.com/mavlink/MAVSDK.git>, checked out at that immutable
commit, and its submodules are initialised recursively.

The target is `linux/arm64` on Ubuntu 24.04. The builder configures a
release shared-library build with:

```text
-DBUILD_SHARED_LIBS=ON
-DBUILD_MAVSDK_SERVER=OFF
-DCMAKE_BUILD_TYPE=Release
```

The application consumes the installed CMake package and the runtime stage
carries `libmavsdk.so` plus the dynamic libraries reported by `ldd` for the
release binary. `mavsdk_server` is not needed by this C++ application and is
explicitly disabled.

## Upstream evidence

- Release inspected: <https://github.com/mavlink/MAVSDK/releases/tag/v3.17.2>
- Release tag/commit: `v3.17.2` /
  `9e3ca17faa84aa868caea10a3bbdab7e53810ced`
- Source-build guidance: <https://mavsdk.mavlink.io/main/en/cpp/guide/build.html>
- C++ packaging guidance: <https://mavsdk.mavlink.io/main/en/cpp/guide/toolchain.html>

GitHub's official v3.17.2 release assets were queried on 2026-10-06. They
include Ubuntu 24.04 **amd64** and Debian 11/12 **arm64** development
packages, but no Ubuntu 24.04 arm64 development package. Therefore no
release-asset checksum applies to the selected source path; the immutable
Git commit is the source identity.

## Rejected alternatives

- `libmavsdk-dev_3.17.2_ubuntu24.04_amd64.deb`: wrong architecture.
- Debian 11/12 arm64 packages: wrong distribution/runtime baseline and
  prohibited by the Phase 4A plan as substitutes for Ubuntu 24.04.
- ARM64 `mavsdk_server` binaries: not the C++ library consumed by
  `nidar-flight`.
- Newer MAVSDK releases: unnecessary version drift; v3.17.2 source is
  available and pinned.
