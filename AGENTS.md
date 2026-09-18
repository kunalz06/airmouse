# NIDAR Codex Instructions

Read `docs/MASTER_PLAN.md` before planning, coding, reviewing, or changing infrastructure.

1. Treat the repository as the source of truth.
2. Follow the architecture and model-routing rules in the master plan.
3. Do not call MAVSDK outside the vehicle adapter.
4. Do not bypass PX4 safety checks.
5. Flight-affecting code requires automated tests, SITL, and independent review.
6. Do not claim success without fresh verification evidence.
7. Use subagents only according to the master plan.
8. Do not run overlapping write agents on the same subsystem.
9. Enforce Docker/build disk limits.
10. Do not leave placeholder production implementations.
