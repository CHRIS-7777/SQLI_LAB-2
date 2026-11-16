"""(Re)create schema + dummy data for every app. Each app module exposes init_db()."""
import sys

from .app import discover

if __name__ == "__main__":
    only = sys.argv[1:]
    for mod in discover():
        slug = mod.META.get("slug", mod.__name__)
        if only and slug not in only:
            continue
        mod.init_db()
        print(f"seeded {slug}")
