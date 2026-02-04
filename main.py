import argparse
from config import Settings
from runner import run_all

def main():
    parser = argparse.ArgumentParser(prog="aws-audit-tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run inventory + cloudmapper")
    run.add_argument("--regions", help="CSV regions override (ex: us-east-1,us-west-2)")
    run.add_argument("--cloudmapper-dir", help="Path to cloudmapper repo")

    args = parser.parse_args()
    s = Settings()

    if args.regions:
        s.regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    if args.cloudmapper_dir:
        s.cloudmapper_dir = args.cloudmapper_dir

    out = run_all(s)
    print(f"✅ Run completed. Outputs at: {out}")


if __name__ == "__main__":
    main()
