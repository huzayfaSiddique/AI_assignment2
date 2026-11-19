from pathlib import Path

GRADE_BANDS: tuple[tuple[int, float], ...] = (
    (85, 4.0),
    (80, 3.7),
    (75, 3.3),
    (70, 3.0),
    (65, 2.7),
    (61, 2.3),
    (58, 2.0),
    (55, 1.7),
    (50, 1.0),
)

FAIL_GRADE_POINTS = 0.0


def marks_to_grade_points(marks: int) -> float:
    """
    Convert a numeric mark (0-100) to PUCIT grade points.
    Use this whenever the user gives raw marks (e.g. "I got 78 in AI") and you
    need the grade-point value before computing a GPA. Returns the plain error
    string "Error: marks must be an integer between 0 and 100" for invalid
    input instead of raising.
    """
    print(f"[TOOL] marks_to_grade_points(marks={marks!r})")
    if isinstance(marks, bool) or not isinstance(marks, int) or not 0 <= marks <= 100:
        err = "Error: marks must be an integer between 0 and 100"
        print(f"[WARN] marks_to_grade_points -> {err}")
        return err
    for threshold, points in GRADE_BANDS:
        if marks >= threshold:
            print(f"[TOOL] marks_to_grade_points -> marks={marks} => {points} grade points")
            return points
    print(f"[TOOL] marks_to_grade_points -> marks={marks} => 0.0 (fail)")
    return FAIL_GRADE_POINTS


SEMESTER_CREDIT_HOURS: dict[int, float] = {
    1: 15.5,
    2: 15.5,
    3: 16.5,
    4: 16.5,
    5: 18.5,
    6: 18.5,
    7: 18.5,
    8: 14.5,
}

TOTAL_DEGREE_CREDIT_HOURS = 134.0

COURSES: dict[int, list[tuple[str, str, float]]] = {
    1: [("MS-251", "Probability & Statistics", 3.0),
        ("GE-160", "Applications of ICT", 3.0),
        ("GE-169", "Applied Physics", 3.0),
        ("GE-167", "Discrete Structures", 3.0),
        ("HQ-001", "Quran Translation - I", 0.5),
        ("GE-190", "Functional English", 3.0)],
    2: [("CC-112", "Programming Fundamentals", 3.0),
        ("CC-112-L", "Programming Fundamentals Lab", 1.0),
        ("CC-110", "Digital Logic Design", 2.0),
        ("CC-110-L", "Digital Logic Design Lab", 1.0),
        ("MS-252", "Linear Algebra", 3.0),
        ("GE-191", "Expository Writing", 3.0),
        ("GE-163", "Islamic Studies", 2.0),
        ("HQ-002", "Quran Translation - II", 0.5)],
    3: [("CC-211", "Object Oriented Programming", 3.0),
        ("CC-211-L", "Object Oriented Programming Lab", 1.0),
        ("CC-215", "Database Systems", 3.0),
        ("CC-215-L", "Database Systems Lab", 1.0),
        ("CC-210", "Computer Organization & Assembly Language", 3.0),
        ("GE-162", "Calculus & Analytical Geometry", 3.0),
        ("GE-192", "Introduction to Management", 2.0),
        ("HQ-003", "Quran Translation - III", 0.5)],
    4: [("CC-213", "Data Structures", 3.0),
        ("CC-213-L", "Data Structures Lab", 1.0),
        ("CC-312", "Information Security", 3.0),
        ("CC-214", "Computer Networks", 3.0),
        ("CC-212", "Software Engineering", 3.0),
        ("DC-220", "Advanced Database Management Systems", 3.0),
        ("HQ-004", "Quran Translation - IV", 0.5)],
    5: [("CC-313", "Analysis of Algorithms", 3.0),
        ("CC-310", "Artificial Intelligence", 3.0),
        ("DC-320", "Theory of Automata and Formal Languages", 3.0),
        ("DC-321", "Human Computer Interaction", 3.0),
        ("DC-322", "Computer Architecture", 3.0),
        ("EC-330", "Web Technologies / Elective", 3.0),
        ("HQ-005", "Quran Translation - V", 0.5)],
    6: [("CC-311", "Operating Systems", 3.0),
        ("EC-333", "Mobile Application Development / Elective", 3.0),
        ("EC-324", "Software Construction & Development / Elective", 3.0),
        ("EC-335", "Machine Learning / Elective", 3.0),
        ("EC-334", "Game Design and Development / Elective", 3.0),
        ("MS-253", "Multivariable Calculus", 3.0),
        ("HQ-006", "Quran Translation - VI", 0.5)],
    7: [("CC-411", "Final Year Project - I", 2.0),
        ("DC-328", "Parallel & Distributed Computing", 3.0),
        ("EC-345", "Computer Vision / Elective", 3.0),
        ("EC-425", "Software Quality Engineering / Elective", 3.0),
        ("MS-254", "Technical and Business Writing", 3.0),
        ("GE-263", "Entrepreneurship", 2.0),
        ("GE-262", "Professional Practices", 2.0),
        ("HQ-007", "Quran Translation - VII", 0.5)],
    8: [("CC-412", "Final Year Project - II", 4.0),
        ("DC-421", "Compiler Construction", 3.0),
        ("UE-272", "Introduction to Marketing", 3.0),
        ("GE-168", "Ideology and Constitution of Pakistan", 2.0),
        ("GE-363", "Civics and Community Engagement", 2.0),
        ("HQ-008", "Quran Translation - VIII", 0.5)],
}


def calculate_semester_gpa(grade_points: list[float], credit_hours: list[float]) -> float:
    """
    Calculate a single semester's credit-weighted GPA.
    Use this once you have grade points (from marks_to_grade_points or given
    directly) and credit hours for every course in one semester.
    Formula: sum(grade_points x credit_hours) / sum(credit_hours).
    """
    print(f"[TOOL] calculate_semester_gpa(grade_points={grade_points}, credit_hours={credit_hours})")
    if not isinstance(grade_points, (list, tuple)) or not isinstance(credit_hours, (list, tuple)):
        err = "Error: grade_points and credit_hours must both be lists of numbers"
        print(f"[WARN] calculate_semester_gpa -> {err}")
        return err
    if not grade_points or not credit_hours:
        err = "Error: grade_points and credit_hours must not be empty"
        print(f"[WARN] calculate_semester_gpa -> {err}")
        return err
    if len(grade_points) != len(credit_hours):
        err = "Error: grade_points and credit_hours must be the same length"
        print(f"[WARN] calculate_semester_gpa -> {err}")
        return err
    for gp in grade_points:
        if isinstance(gp, bool) or not isinstance(gp, (int, float)) or not 0 <= gp <= 4.0:
            err = "Error: every grade point must be a number between 0 and 4.0"
            print(f"[WARN] calculate_semester_gpa -> {err} (got {gp!r})")
            return err
    for ch in credit_hours:
        if isinstance(ch, bool) or not isinstance(ch, (int, float)) or ch <= 0:
            err = "Error: every credit hour value must be a number greater than 0"
            print(f"[WARN] calculate_semester_gpa -> {err} (got {ch!r})")
            return err
    result = sum(gp * ch for gp, ch in zip(grade_points, credit_hours)) / sum(credit_hours)
    print(f"[TOOL] calculate_semester_gpa -> {len(grade_points)} courses, "
          f"total_ch={sum(credit_hours):.1f} => GPA={result:.4f}")
    return result


def calculate_new_cgpa(current_cgpa: float, completed_credit_hours: float,
                       semester_gpa: float, semester_credit_hours: float) -> float:
    """
    Project the new CGPA after adding one semester's GPA to the existing record.
    Use this when the user gives their current CGPA + completed credit hours and
    asks what a hypothetical or actual semester GPA does to their CGPA.
    Formula: (current_cgpa x completed_ch + semester_gpa x semester_ch)
             / (completed_ch + semester_ch).
    """
    print(f"[TOOL] calculate_new_cgpa(current_cgpa={current_cgpa}, "
          f"completed_ch={completed_credit_hours}, "
          f"semester_gpa={semester_gpa}, semester_ch={semester_credit_hours})")
    for value, label in ((current_cgpa, "current_cgpa"), (semester_gpa, "semester_gpa")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 4.0:
            err = f"Error: {label} must be a number between 0 and 4.0"
            print(f"[WARN] calculate_new_cgpa -> {err}")
            return err
    for value, label in ((completed_credit_hours, "completed_credit_hours"),
                         (semester_credit_hours, "semester_credit_hours")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            err = f"Error: {label} must be a number that is 0 or greater"
            print(f"[WARN] calculate_new_cgpa -> {err}")
            return err
    total = completed_credit_hours + semester_credit_hours
    if total <= 0:
        err = "Error: completed_credit_hours + semester_credit_hours must be greater than 0"
        print(f"[WARN] calculate_new_cgpa -> {err}")
        return err
    result = (current_cgpa * completed_credit_hours + semester_gpa * semester_credit_hours) / total
    print(f"[TOOL] calculate_new_cgpa -> current={current_cgpa:.2f} + "
          f"sem_gpa={semester_gpa:.2f} ({semester_credit_hours:.1f} ch) => new_cgpa={result:.4f}")
    return result


def required_gpa_for_target(target_cgpa: float, current_cgpa: float,
                            completed_credit_hours: float,
                            remaining_credit_hours: float) -> float:
    """
    Calculate the GPA needed over the remaining credit hours to reach a target
    CGPA. Use this for "what GPA do I need to graduate/reach X" style questions.
    The result may exceed 4.0, which means the target is impossible over that
    horizon; widen the horizon (more remaining_credit_hours) and call again.
    Formula: (target_cgpa x (completed_ch + remaining_ch)
             - current_cgpa x completed_ch) / remaining_ch.
    """
    print(f"[TOOL] required_gpa_for_target(target={target_cgpa}, current={current_cgpa}, "
          f"completed_ch={completed_credit_hours}, remaining_ch={remaining_credit_hours})")
    for value, label in ((target_cgpa, "target_cgpa"), (current_cgpa, "current_cgpa")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 4.0:
            err = f"Error: {label} must be a number between 0 and 4.0"
            print(f"[WARN] required_gpa_for_target -> {err}")
            return err
    if isinstance(completed_credit_hours, bool) or not isinstance(completed_credit_hours, (int, float)) \
            or completed_credit_hours < 0:
        err = "Error: completed_credit_hours must be a number that is 0 or greater"
        print(f"[WARN] required_gpa_for_target -> {err}")
        return err
    if isinstance(remaining_credit_hours, bool) or not isinstance(remaining_credit_hours, (int, float)) \
            or remaining_credit_hours <= 0:
        err = "Error: remaining_credit_hours must be a number greater than 0"
        print(f"[WARN] required_gpa_for_target -> {err}")
        return err
    numerator = target_cgpa * (completed_credit_hours + remaining_credit_hours) \
        - current_cgpa * completed_credit_hours
    result = numerator / remaining_credit_hours
    flag = "  <-- ABOVE 4.0, horizon too narrow" if result > 4.0 else ""
    print(f"[TOOL] required_gpa_for_target -> needed_gpa={result:.4f}{flag}")
    return result


def get_semester_courses(semester: int) -> str:
    """
    Return the graded courses and credit hours for a given semester (1-8),
    excluding Math Deficiency courses. Use this when the user asks what they are
    taking, or when you need the credit hours for a semester GPA calculation and
    the user has not listed them. The last line gives the semester's total credit
    hours, so you never have to add them up yourself.
    """
    print(f"[TOOL] get_semester_courses(semester={semester!r})")
    if isinstance(semester, bool) or not isinstance(semester, int) or not 1 <= semester <= 8:
        err = "Error: semester must be between 1 and 8"
        print(f"[WARN] get_semester_courses -> {err} (got {semester!r})")
        return err
    rows = COURSES[semester]
    total = sum(ch for _, _, ch in rows)
    print(f"[TOOL] get_semester_courses -> semester={semester}, "
          f"courses={len(rows)}, total_ch={total:.1f}")
    listing = [f"{code}  {title}  ({ch} credit hours)" for code, title, ch in rows]
    return f"Semester {semester} - {len(rows)} courses, {total} credit hours total:\n" + "\n".join(listing)


def get_remaining_credit_hours(current_semester: int) -> float:
    """
    Total the graded credit hours remaining after completing a given semester,
    i.e. every semester from current_semester+1 up to semester 8. Use this when
    calculating a required GPA for the rest of the degree and the user has not
    given the remaining credit hours directly. Semester 8 leaves 0.0 remaining.
    """
    print(f"[TOOL] get_remaining_credit_hours(current_semester={current_semester!r})")
    if isinstance(current_semester, bool) or not isinstance(current_semester, int) \
            or not 1 <= current_semester <= 8:
        err = "Error: semester must be between 1 and 8"
        print(f"[WARN] get_remaining_credit_hours -> {err} (got {current_semester!r})")
        return err
    result = float(sum(SEMESTER_CREDIT_HOURS[s] for s in range(current_semester + 1, 9)))
    print(f"[TOOL] get_remaining_credit_hours -> after semester {current_semester}, "
          f"{result:.1f} credit hours remaining")
    return result


def save_report(filename: str, content: str) -> str:
    """
    Save a text summary of a GPA/CGPA result to disk and return a confirmation.
    Only use this after producing a real result worth keeping (a semester GPA, a
    projected CGPA, or a plan for reaching a target) and only after the user has
    explicitly asked you to save it. A .txt extension is added if none is given.
    """
    content_len = len(content) if isinstance(content, str) else -1
    print(f"[TOOL] save_report(filename={filename!r}, content_length={content_len})")
    if not isinstance(filename, str) or not filename.strip():
        err = "Error: filename must be a non-empty string"
        print(f"[WARN] save_report -> {err}")
        return err
    if not isinstance(content, str) or not content.strip():
        err = "Error: content must be a non-empty string"
        print(f"[WARN] save_report -> {err}")
        return err
    path = Path(filename.strip())
    if not path.suffix:
        path = path.with_suffix(".txt")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] save_report -> failed to write '{path}': {exc}")
        return f"Error: could not save report: {exc}"
    print(f"[TOOL] save_report -> written to '{path}' ({path.stat().st_size} bytes)")
    return f"Saved report to {path}"
