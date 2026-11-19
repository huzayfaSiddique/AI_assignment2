import os
import sys
from pathlib import Path

# Ensure tools can be imported whether run from root or inside server/
sys.path.insert(0, str(Path(__file__).parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from fastmcp import FastMCP
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

# Expose all 7 GPA/CGPA tools on the FastMCP server
mcp.tool(marks_to_grade_points)
mcp.tool(calculate_semester_gpa)
mcp.tool(calculate_new_cgpa)
mcp.tool(required_gpa_for_target)
mcp.tool(get_semester_courses)
mcp.tool(get_remaining_credit_hours)
mcp.tool(save_report)

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting FastMCP server on http://{host}:{port}/mcp ...")
    mcp.run(transport="http", host=host, port=port)
