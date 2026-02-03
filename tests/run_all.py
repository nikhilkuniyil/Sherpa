#!/usr/bin/env python3
"""
Run all Sherpa tests.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 70)
    print("SHERPA - FULL TEST SUITE")
    print("=" * 70)

    total_passed = 0
    total_failed = 0

    # Run coach tests
    print("\n\n--- Running Core Tests ---\n")
    from tests.test_coach import run_all_tests as run_coach_tests
    result = run_coach_tests()
    if result == 0:
        total_passed += 4  # 4 tests in coach
    else:
        total_failed += 1

    # Run tutoring tests
    print("\n\n--- Running Tutoring Tests ---\n")
    from tests.test_tutoring import run_all_tests as run_tutoring_tests
    result = run_tutoring_tests()
    if result == 0:
        total_passed += 8  # 8 tests in tutoring
    else:
        total_failed += 1

    # Final summary
    print("\n" + "=" * 70)
    print("FULL TEST SUITE SUMMARY")
    print("=" * 70)
    print(f"\nTotal test groups passed: {2 - total_failed}/2")

    if total_failed == 0:
        print("\nAll test suites passed!")
        return 0
    else:
        print(f"\n{total_failed} test suite(s) had failures.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
