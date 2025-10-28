from pathlib import Path

from modify import filter_berlin, download_thumb, compare_thumbs

def header(msg: str):
    print("\n" + "=" * 80)
    print(msg)
    print("=" * 80 + "\n")

def ensure_symlink(src: Path, link: Path):
    """Make symlink link -> src if needed (so compare finds images)."""
    if link.exists():
        return
    if not src.exists():
        return
    try:
        link.symlink_to(src, target_is_directory=True)
        print(f"[info] Created symlink: {link} -> {src}")
    except Exception as e:
        print(f"[warn] Could not create symlink {link} -> {src}: {e}")

def main():
    # Step 1
    header("Step 1/3 — filter_berlin")
    filter_berlin.main()

    # Step 2
    header("Step 2/3 — download_thumb")
    download_thumb.main()

    # Ensure symlink if compare expects thumb_1024/ but downloads live in 1024/
    ensure_symlink(Path("singapore"), Path("thumb_1024"))

    # Step 3
    header("Step 3/3 — compare_thumbs")
    compare_thumbs.main()

    header("Pipeline finished")

if __name__ == "__main__":
    main()