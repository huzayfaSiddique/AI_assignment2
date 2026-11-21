import os
import sys
from pathlib import Path

# Ensure tools can be imported whether run from root or inside server/
sys.path.insert(0, str(Path(__file__).parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from fastmcp import FastMCP
from starlette.responses import PlainTextResponse
from tools import (
    calculate_new_cgpa,
    calculate_semester_gpa,
    get_remaining_credit_hours,
    get_semester_courses,
    marks_to_grade_points,
    required_gpa_for_target,
    save_report,
)

mcp = FastMCP("cgpa")


# Health check routes so uptime monitors (cron-job.org / UptimeRobot) receive HTTP 200 OK
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return PlainTextResponse("OK", status_code=200)


@mcp.custom_route("/", methods=["GET"])
async def root_check(request):
    return PlainTextResponse("PUCIT GPA MCP Server is running!", status_code=200)


# Expose all 7 GPA/CGPA tools on the FastMCP server

mcp.tool(marks_to_grade_points)
mcp.tool(calculate_semester_gpa)
mcp.tool(calculate_new_cgpa)
mcp.tool(required_gpa_for_target)
mcp.tool(get_semester_courses)
mcp.tool(get_remaining_credit_hours)
mcp.tool(save_report)

if __name__ == "__main__":
    default_host = "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"
    host = os.getenv("HOST", default_host)
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting FastMCP server on http://{host}:{port}/mcp ...")
    mcp.run(transport="http", host=host, port=port)
