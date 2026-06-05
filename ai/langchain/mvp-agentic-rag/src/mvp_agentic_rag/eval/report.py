from mvp_agentic_rag.eval.runner import EvalReport


def to_json(report: EvalReport) -> dict:
    return {
        "pass_rate": report.pass_rate,
        "passed_count": report.passed_count,
        "total": len(report.cases),
        "cases": {
            c.case_id: {
                "passed": c.result.passed,
                "must_include_ok": c.result.must_include_ok,
                "route_ok": c.result.route_ok,
                "citation_ok": c.result.citation_ok,
                "refusal_ok": c.result.refusal_ok,
                "route": c.route,
            }
            for c in report.cases
        },
    }


def to_markdown(report: EvalReport) -> str:
    lines = [
        "# Eval Report",
        "",
        f"- pass_rate: {report.pass_rate:.2%}",
        f"- passed: {report.passed_count}/{len(report.cases)}",
        "",
        "| case | passed | must_include | route | citation | refusal |",
        "|------|--------|--------------|-------|----------|---------|",
    ]
    for c in report.cases:
        r = c.result
        lines.append(
            f"| {c.case_id} | {'✅' if r.passed else '❌'} | {r.must_include_ok} | "
            f"{r.route_ok} | {r.citation_ok} | {r.refusal_ok} |"
        )
    return "\n".join(lines)


def diff_reports(prev: dict, curr: dict) -> list[str]:
    """返回回归的 case id 列表:在 prev 通过、在 curr 失败。"""
    regressions = []
    prev_cases = prev.get("cases", {})
    curr_cases = curr.get("cases", {})
    for cid, pinfo in prev_cases.items():
        cinfo = curr_cases.get(cid)
        if pinfo.get("passed") and cinfo is not None and not cinfo.get("passed"):
            regressions.append(cid)
    return regressions
