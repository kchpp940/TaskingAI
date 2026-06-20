import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional


logger = logging.getLogger(__name__)


class Phase(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    CACHE = "cache"
    SERVICE = "service"
    APPLICATION = "application"


class HookSeverity(str, Enum):
    CRITICAL = "critical"
    DEGRADABLE = "degradable"


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class StartupHook:
    name: str
    phase: Phase
    fn: Callable[..., Coroutine]
    severity: HookSeverity = HookSeverity.CRITICAL
    fallback_fn: Optional[Callable[..., Coroutine]] = None
    description: str = ""


@dataclass
class ShutdownHook:
    name: str
    fn: Callable[..., Coroutine]
    description: str = ""


@dataclass
class HookResult:
    name: str
    phase: Phase
    success: bool
    degraded: bool
    elapsed: float
    error: Optional[str] = None


@dataclass
class PhaseReport:
    phase: Phase
    results: List[HookResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def any_degraded(self) -> bool:
        return any(r.degraded for r in self.results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "all_passed": self.all_passed,
            "any_degraded": self.any_degraded,
            "hooks": [
                {
                    "name": r.name,
                    "success": r.success,
                    "degraded": r.degraded,
                    "elapsed": r.elapsed,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


@dataclass
class LifecycleState:
    service_name: str
    status: ServiceStatus = ServiceStatus.PENDING
    phase_reports: List[PhaseReport] = field(default_factory=list)
    degraded_services: Dict[str, str] = field(default_factory=dict)
    failure_reason: Optional[str] = None
    failed_phase: Optional[Phase] = None
    total_elapsed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "degraded_services": dict(self.degraded_services),
            "failure_reason": self.failure_reason,
            "failed_phase": self.failed_phase.value if self.failed_phase else None,
            "total_elapsed": round(self.total_elapsed, 3),
            "phases": [p.to_dict() for p in self.phase_reports],
        }


class LifecycleManager:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._startup_hooks: Dict[Phase, List[StartupHook]] = {p: [] for p in Phase}
        self._shutdown_hooks: List[ShutdownHook] = []
        self._startup_results: List[HookResult] = []
        self._phase_reports: List[PhaseReport] = []
        self._degraded_state: Dict[str, str] = {}
        self._state = LifecycleState(service_name=service_name)

    def register_startup(
        self,
        name: str,
        phase: Phase,
        fn: Callable[..., Coroutine],
        severity: HookSeverity = HookSeverity.CRITICAL,
        fallback_fn: Optional[Callable[..., Coroutine]] = None,
        description: str = "",
    ):
        hook = StartupHook(
            name=name,
            phase=phase,
            fn=fn,
            severity=severity,
            fallback_fn=fallback_fn,
            description=description,
        )
        self._startup_hooks[phase].append(hook)
        logger.debug(
            f"[{self.service_name}] Registered startup hook: "
            f"name={name}, phase={phase.value}, severity={severity.value}"
        )

    def register_shutdown(
        self,
        name: str,
        fn: Callable[..., Coroutine],
        description: str = "",
    ):
        hook = ShutdownHook(name=name, fn=fn, description=description)
        self._shutdown_hooks.append(hook)
        logger.debug(
            f"[{self.service_name}] Registered shutdown hook: name={name}"
        )

    @property
    def state(self) -> LifecycleState:
        return self._state

    @property
    def status(self) -> ServiceStatus:
        return self._state.status

    @property
    def degraded_services(self) -> Dict[str, str]:
        return dict(self._degraded_state)

    @property
    def phase_reports(self) -> List[PhaseReport]:
        return list(self._phase_reports)

    @property
    def is_healthy(self) -> bool:
        return self._state.status == ServiceStatus.HEALTHY

    @property
    def is_degraded(self) -> bool:
        return self._state.status == ServiceStatus.DEGRADED

    @property
    def is_failed(self) -> bool:
        return self._state.status == ServiceStatus.FAILED

    def attach_to_app(self, app: Any) -> None:
        app.state.lifecycle = self
        app.state.lifecycle_state = self._state
        app.state.lifecycle_status = self._state.status

    async def run_startup(self) -> bool:
        self._startup_results.clear()
        self._phase_reports.clear()
        self._degraded_state.clear()
        self._state = LifecycleState(service_name=self.service_name)

        logger.info(f"[{self.service_name}] ========== Service Startup ==========")
        t_start = time.monotonic()
        overall_success = True
        failed_phase: Optional[Phase] = None
        failure_reason: Optional[str] = None

        for phase in Phase:
            hooks = self._startup_hooks[phase]
            if not hooks:
                continue

            report = PhaseReport(phase=phase)
            logger.info(
                f"[{self.service_name}] >>> Phase: {phase.value} "
                f"({len(hooks)} hook(s))"
            )

            for hook in hooks:
                result = await self._execute_startup_hook(hook)
                report.results.append(result)
                self._startup_results.append(result)

                if not result.success:
                    overall_success = False

            self._phase_reports.append(report)
            self._log_phase_summary(report)

            critical_failed = [
                r for r in report.results if not r.success and not r.degraded
            ]
            if critical_failed:
                failed_phase = phase
                failure_reason = "; ".join(
                    f"{r.name}: {r.error}" for r in critical_failed if r.error
                )
                logger.error(
                    f"[{self.service_name}] !!! Critical failure in phase "
                    f"'{phase.value}', aborting startup"
                )
                await self._run_emergency_shutdown()
                overall_success = False
                break

        total_elapsed = time.monotonic() - t_start

        if not overall_success:
            self._state.status = ServiceStatus.FAILED
            self._state.failed_phase = failed_phase
            self._state.failure_reason = failure_reason
        elif self._degraded_state:
            self._state.status = ServiceStatus.DEGRADED
        else:
            self._state.status = ServiceStatus.HEALTHY

        self._state.phase_reports = list(self._phase_reports)
        self._state.degraded_services = dict(self._degraded_state)
        self._state.total_elapsed = total_elapsed

        self._log_startup_summary()
        return overall_success

    async def run_shutdown(self):
        logger.info(f"[{self.service_name}] ========== Service Shutdown ==========")
        for hook in reversed(self._shutdown_hooks):
            t0 = time.monotonic()
            try:
                logger.info(
                    f"[{self.service_name}] Shutdown: {hook.name}"
                    + (f" - {hook.description}" if hook.description else "")
                )
                await hook.fn()
                elapsed = time.monotonic() - t0
                logger.info(
                    f"[{self.service_name}] Shutdown: {hook.name} "
                    f"completed ({elapsed:.3f}s)"
                )
            except Exception as e:
                elapsed = time.monotonic() - t0
                logger.error(
                    f"[{self.service_name}] Shutdown: {hook.name} "
                    f"failed ({elapsed:.3f}s): {e}"
                )
        logger.info(f"[{self.service_name}] ========== Shutdown Complete ==========")

    async def _execute_startup_hook(self, hook: StartupHook) -> HookResult:
        desc = f" - {hook.description}" if hook.description else ""
        logger.info(
            f"[{self.service_name}] Starting: {hook.name} "
            f"[{hook.phase.value}/{hook.severity.value}]{desc}"
        )
        t0 = time.monotonic()
        try:
            await hook.fn()
            elapsed = time.monotonic() - t0
            logger.info(
                f"[{self.service_name}] OK: {hook.name} ({elapsed:.3f}s)"
            )
            return HookResult(
                name=hook.name,
                phase=hook.phase,
                success=True,
                degraded=False,
                elapsed=elapsed,
            )
        except Exception as e:
            elapsed = time.monotonic() - t0
            if hook.severity == HookSeverity.DEGRADABLE:
                degradation_msg = str(e)
                self._degraded_state[hook.name] = degradation_msg
                if hook.fallback_fn:
                    try:
                        await hook.fallback_fn()
                        logger.warning(
                            f"[{self.service_name}] DEGRADED: {hook.name} "
                            f"({elapsed:.3f}s) - {degradation_msg}, "
                            f"fallback applied"
                        )
                    except Exception as fb_err:
                        logger.error(
                            f"[{self.service_name}] DEGRADED: {hook.name} "
                            f"({elapsed:.3f}s) - {degradation_msg}, "
                            f"fallback also failed: {fb_err}"
                        )
                else:
                    logger.warning(
                        f"[{self.service_name}] DEGRADED: {hook.name} "
                        f"({elapsed:.3f}s) - {degradation_msg}, "
                        f"running without this capability"
                    )
                return HookResult(
                    name=hook.name,
                    phase=hook.phase,
                    success=True,
                    degraded=True,
                    elapsed=elapsed,
                    error=degradation_msg,
                )
            else:
                logger.error(
                    f"[{self.service_name}] FAILED: {hook.name} "
                    f"({elapsed:.3f}s) - {e}"
                )
                return HookResult(
                    name=hook.name,
                    phase=hook.phase,
                    success=False,
                    degraded=False,
                    elapsed=elapsed,
                    error=str(e),
                )

    async def _run_emergency_shutdown(self):
        logger.warning(
            f"[{self.service_name}] Running emergency shutdown "
            f"after critical failure..."
        )
        for hook in reversed(self._shutdown_hooks):
            t0 = time.monotonic()
            try:
                await hook.fn()
                logger.info(
                    f"[{self.service_name}] Emergency shutdown: "
                    f"{hook.name} completed ({time.monotonic() - t0:.3f}s)"
                )
            except Exception as e:
                logger.error(
                    f"[{self.service_name}] Emergency shutdown: "
                    f"{hook.name} failed: {e}"
                )

    def _log_phase_summary(self, report: PhaseReport):
        total = len(report.results)
        ok = sum(1 for r in report.results if r.success and not r.degraded)
        degraded = sum(1 for r in report.results if r.degraded)
        failed = sum(1 for r in report.results if not r.success)
        logger.info(
            f"[{self.service_name}] <<< Phase '{report.phase.value}': "
            f"{total} total, {ok} ok, {degraded} degraded, {failed} failed"
        )

    def _log_startup_summary(self):
        total = len(self._startup_results)
        ok = sum(1 for r in self._startup_results if r.success and not r.degraded)
        degraded = sum(1 for r in self._startup_results if r.degraded)
        failed = sum(1 for r in self._startup_results if not r.success)

        logger.info(f"[{self.service_name}] ========== Startup Summary ==========")
        logger.info(
            f"[{self.service_name}] Status: {self._state.status.value}"
        )
        logger.info(
            f"[{self.service_name}] Total: {total}, "
            f"OK: {ok}, Degraded: {degraded}, Failed: {failed}"
        )
        logger.info(
            f"[{self.service_name}] Elapsed: {self._state.total_elapsed:.3f}s"
        )
        if self._degraded_state:
            logger.warning(
                f"[{self.service_name}] Degraded services:"
            )
            for name, reason in self._degraded_state.items():
                logger.warning(
                    f"[{self.service_name}]   - {name}: {reason}"
                )
        if self._state.failure_reason:
            logger.error(
                f"[{self.service_name}] Failure reason: {self._state.failure_reason}"
            )
        logger.info(f"[{self.service_name}] ======================================")
