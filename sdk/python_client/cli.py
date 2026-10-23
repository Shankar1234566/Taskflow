"""
Command-Line Interface (CLI) for Taskflow Pro (`taskflow-cli`).
Provides shell commands for task management, sprint status, and user management.
"""
import argparse
import sys
from .client import TaskflowClient
from .exceptions import TaskflowAPIError


def main():
    parser = argparse.ArgumentParser(description="Taskflow Enterprise CLI Utility")
    parser.add_argument("--url", default="http://127.0.0.1:5000", help="Taskflow server base URL")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # login
    login_p = subparsers.add_parser("login", help="Authenticate with email and password")
    login_p.add_argument("email", help="Account email")
    login_p.add_argument("--password", default="password123", help="Account password")

    # tasks list
    list_p = subparsers.add_parser("list", help="List active workspace tasks")
    list_p.add_argument("--category", help="Filter by category")
    list_p.add_argument("--status", help="Filter by status")

    # tasks create
    create_p = subparsers.add_parser("create", help="Create a new task")
    create_p.add_argument("title", help="Task title")
    create_p.add_argument("--priority", default="Medium", choices=["Critical", "High", "Medium", "Low"])
    create_p.add_argument("--category", default="General")
    create_p.add_argument("--due", help="Due date YYYY-MM-DD")

    # stats
    subparsers.add_parser("stats", help="Show dashboard summary metrics")

    args = parser.parse_args()
    client = TaskflowClient(base_url=args.url)

    try:
        if args.command == "login":
            user = client.login(args.email, args.password)
            print(f"Logged in as {user.username} ({user.role})")
        elif args.command == "list":
            client.login("admin@taskflow.local", "password123")
            tasks = client.list_tasks(category=args.category, status=args.status)
            print(f"{'ID':<6} {'STATUS':<14} {'PRIORITY':<10} {'TITLE'}")
            print("-" * 60)
            for t in tasks:
                print(f"#{t.id:<5} {t.status:<14} {t.priority:<10} {t.title}")
        elif args.command == "create":
            client.login("admin@taskflow.local", "password123")
            t = client.create_task(args.title, priority=args.priority, category=args.category, due_date=args.due)
            print(f"Created task #{t.id}: {t.title} ({t.priority})")
        elif args.command == "stats":
            client.login("admin@taskflow.local", "password123")
            s = client.get_dashboard_stats()
            print("Taskflow Productivity Stats:")
            print(f"  Total Tasks: {s.total}")
            print(f"  Completed:   {s.completed} ({s.completion_percentage}%)")
            print(f"  In Progress: {s.in_progress}")
            print(f"  In Review:   {s.in_review}")
            print(f"  Overdue:     {s.overdue}")
    except TaskflowAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
