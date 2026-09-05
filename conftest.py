from pytest import ExitCode, Session


def pytest_sessionfinish(session: Session, exitstatus: int) -> None:
    if exitstatus == ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = ExitCode.OK
