from backend.app.domain.enums import ErrorCode


def test_optimizer_error_codes_exist():
    assert ErrorCode.SOLVER_NON_CONVERGENCE == "SOLVER_NON_CONVERGENCE"
    assert ErrorCode.INFEASIBLE_CONSTRAINTS == "INFEASIBLE_CONSTRAINTS"
    assert ErrorCode.INDEFINITE_CORRELATION_MATRIX == "INDEFINITE_CORRELATION_MATRIX"
