import argparse
from utils.seeder import ElectionSeeder

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed or delete election data.")
    parser.add_argument("--delete", type=str, help="Filename to delete data for")
    parser.add_argument("--init", action="store_true", help="Initialize database tables")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    
    args = parser.parse_args()
    seeder = ElectionSeeder(max_workers=args.workers)
    
    if args.init:
        seeder.db.init_db()
        print("Database initialized.")
    elif args.delete:
        seeder.db.delete_by_filename(args.delete)
    else:
        seeder.run()
