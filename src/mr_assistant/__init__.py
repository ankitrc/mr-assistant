"""MR Assistant: data access and tools for the agentic assistant.

    from mr_assistant.db import as_employee
    from mr_assistant import tools

    with as_employee(990001) as db:              # acts as BO Karthikeyan R (row-level security applies)
        print(tools.get_rep_kpis(db))
"""

__version__ = "0.5.1"
