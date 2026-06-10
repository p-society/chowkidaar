import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.submission_queue import (
    enqueue_submission,
    get_pending_jobs,
    mark_processed,
    mark_retry,
    mark_failed,
    has_pending_entry
)

async def test_queue_flow():
    print("🚀 Starting Submission Queue Tests...\n")
    
    test_user_id = "TEST_STU_001"
    test_discord_id = 123456789
    test_day = 99
    
    # 1. Test Enqueue
    print("1️⃣ Testing Enqueue...")
    success = enqueue_submission(
        user_id=test_user_id,
        discord_user_id=test_discord_id,
        day=test_day,
        description="Test submission",
        submitted_at=datetime.now(timezone.utc),
        failed_platform="codeforces",
        error_msg="Test Error 502"
    )
    if success:
        print("✅ Successfully enqueued test submission.")
    else:
        print("❌ Failed to enqueue (or already exists).")
        
    # 2. Test Deduplication
    print("\n2️⃣ Testing Deduplication (UNIQUE constraint)...")
    duplicate_success = enqueue_submission(
        user_id=test_user_id,
        discord_user_id=test_discord_id,
        day=test_day,
        description="Duplicate test submission",
        submitted_at=datetime.now(timezone.utc),
        failed_platform="codeforces",
        error_msg="Test Error 502"
    )
    if not duplicate_success:
        print("✅ Deduplication works: duplicate insertion was ignored.")
    else:
        print("❌ Deduplication failed: duplicate was inserted.")

    # 3. Test Checking for Pending Entry
    print("\n3️⃣ Testing has_pending_entry...")
    has_pending = has_pending_entry(test_user_id, test_day)
    if has_pending:
        print("✅ has_pending_entry correctly found the queued item.")
    else:
        print("❌ has_pending_entry failed to find the queued item.")

    # 4. Fetch Pending Jobs
    print("\n4️⃣ Testing Fetch Pending Jobs...")
    jobs = get_pending_jobs()
    test_job = next((j for j in jobs if j["user_id"] == test_user_id and j["day"] == test_day), None)
    
    if test_job:
        print(f"✅ Found test job in pending queue (ID: {test_job['id']}).")
        
        # 5. Test mark_retry
        print("\n5️⃣ Testing mark_retry...")
        mark_retry(test_job['id'])
        print("✅ mark_retry executed successfully (check DB manually for next_retry_at push).")
        
        # 6. Test mark_processed
        print("\n6️⃣ Testing mark_processed...")
        mark_processed(test_job['id'])
        still_pending = has_pending_entry(test_user_id, test_day)
        if not still_pending:
            print("✅ mark_processed worked! Job is no longer pending.")
        else:
            print("❌ mark_processed failed: Job is still pending.")
            
    else:
        print("❌ Could not find test job in pending jobs. (Is next_retry_at in the future?)")
        
    print("\n🎉 Tests completed. Please run scripts/init_db.py first if any tests failed.")

if __name__ == "__main__":
    asyncio.run(test_queue_flow())
