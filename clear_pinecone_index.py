# clear_pinecone_index.py -- Safely wipe all vectors from the active Pinecone index.
#
# Run this BEFORE build_index.py when you want a clean slate.
#
# Usage:
#     python clear_pinecone_index.py

import sys
import time

from config import (
    VECTOR_BACKEND,
    PINECONE_API_KEY,
    get_active_pinecone_index_name,
)


def get_vector_count(index) -> int:
    stats = index.describe_index_stats()
    return stats.get("total_vector_count", 0)


def main():
    print("\n" + "=" * 60)
    print("  Pinecone Index Cleaner")
    print("=" * 60)

    # Guard: only runs in Pinecone mode
    if VECTOR_BACKEND != "pinecone":
        print(f"\n[SKIP] VECTOR_BACKEND is '{VECTOR_BACKEND}', not 'pinecone'.")
        print("       Nothing to clear. Your FAISS index is a local file.")
        print("       To reset FAISS: delete the vector_store/ folder, then run build_index.py")
        sys.exit(0)

    if not PINECONE_API_KEY:
        print("\n[ERROR] PINECONE_API_KEY is not set in .env")
        sys.exit(1)

    # Connect
    from pinecone import Pinecone
    pc         = Pinecone(api_key=PINECONE_API_KEY)
    index_name = get_active_pinecone_index_name()
    index      = pc.Index(index_name)

    print(f"\n  Index name    : {index_name}")
    print(f"  Pinecone key  : {PINECONE_API_KEY[:4]}****")

    # Show BEFORE count
    print("\n[INFO] Fetching current index stats ...")
    before_count = get_vector_count(index)
    stats        = index.describe_index_stats()

    print(f"\n  Total vectors  : {before_count:,}")

    namespaces = stats.get("namespaces", {})
    if namespaces:
        print("  Namespaces:")
        for ns_name, ns_data in namespaces.items():
            label = "(default)" if ns_name == "" else ns_name
            print(f"    '{label}' -> {ns_data.get('vector_count', 0):,} vectors")
    else:
        print("  Namespaces     : (default namespace, no named namespaces)")

    if before_count == 0:
        print("\n[INFO] Index is already empty. Nothing to delete.")
        print("       You can run build_index.py directly.\n")
        sys.exit(0)

    # Confirmation prompt
    print(f"\n[WARNING] This will permanently delete ALL {before_count:,} vectors")
    print(f"          from index '{index_name}' (default namespace).")
    print("          This cannot be undone. Run build_index.py to re-populate.")
    print()

    confirm = input("  Type  yes  to confirm, anything else to cancel: ").strip().lower()

    if confirm != "yes":
        print("\n[CANCELLED] No vectors were deleted.")
        sys.exit(0)

    # Delete
    print(f"\n[DELETE] Deleting all vectors in default namespace ...")
    index.delete(delete_all=True, namespace="")

    # Wait for Pinecone serverless to process
    print("[WAIT]   Waiting 5 seconds for Pinecone to confirm ...")
    time.sleep(5)

    # Verify AFTER count
    after_count = get_vector_count(index)
    print(f"\n[VERIFY] Vectors before : {before_count:,}")
    print(f"[VERIFY] Vectors after  : {after_count:,}")

    if after_count == 0:
        print("\n[OK]  Index cleared successfully.")
        print("\nNext step -> rebuild the index:")
        print("   python build_index.py\n")
    else:
        print(f"\n[WARN] {after_count:,} vectors still remain.")
        print("       Pinecone serverless can take up to 60 seconds to process deletes.")
        print("       Wait a moment then re-run this script to verify,")
        print("       OR proceed with build_index.py -- new vectors will overwrite old ones.\n")


if __name__ == "__main__":
    main()
