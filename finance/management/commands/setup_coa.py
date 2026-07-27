#!/usr/bin/env python
"""
Run this script to set up the complete, corrected Chart of Accounts.
Usage:
    python manage.py shell < setup_corrected_coa.py
OR
    python manage.py shell
    >>> exec(open('setup_corrected_coa.py').read())
"""
import sys
from django.db import transaction
from finance.models import ChartOfAccount

# ───────────────────────────────────────────────────────────────
# Complete COA structure – including missing accounts (1001, 1002,
# 1200, 2000, 2001, 2100) placed in the correct hierarchy.
# ───────────────────────────────────────────────────────────────
COA_STRUCTURE = [
    {
        "code": "1000",
        "name": "Assets",
        "type": "asset",
        "children": [
            {
                "code": "1100",
                "name": "Current Assets",
                "type": "asset",
                "children": [
                    {"code": "1001", "name": "Cash", "type": "asset"},          # ✅ ADDED
                    {"code": "1110", "name": "Cash in Bank", "type": "asset"},
                    {"code": "1120", "name": "Cash on Hand", "type": "asset"},
                    {"code": "1130", "name": "MTN Mobile Money", "type": "asset"},
                    {"code": "1140", "name": "Airtel Money", "type": "asset"},
                ]
            },
            {
                "code": "1200",
                "name": "Loan Portfolio",
                "type": "asset",
                "children": [
                    {"code": "1002", "name": "Loan Portfolio", "type": "asset"},   # ✅ ADDED
                    {"code": "1200", "name": "Principal Recovery", "type": "asset"}, # ✅ ADDED
                    {"code": "1210", "name": "Loans to Members", "type": "asset"},
                    {"code": "1220", "name": "Interest Receivable", "type": "asset"},
                ]
            },
            {
                "code": "1300",
                "name": "Fixed Assets",
                "type": "asset",
                "children": [
                    {"code": "1310", "name": "Motorcycles", "type": "asset"},
                    {"code": "1320", "name": "Office Equipment", "type": "asset"},
                ]
            },
            {
                "code": "1400",
                "name": "Other Assets",
                "type": "asset",
                "children": [
                    {"code": "1410", "name": "Prepaid Rent", "type": "asset"},
                    {"code": "1420", "name": "Stationery Stock", "type": "asset"},
                ]
            }
        ]
    },
    {
        "code": "2000",
        "name": "Liabilities",
        "type": "liability",
        "children": [
            {"code": "2001", "name": "Member Savings", "type": "liability"},   # ✅ ADDED
            {"code": "2100", "name": "Member Savings", "type": "liability"},   # existing – keep both
            {"code": "2200", "name": "External Loans", "type": "liability"},
            {"code": "2300", "name": "Accrued Expenses", "type": "liability"},
        ]
    },
    {
        "code": "3000",
        "name": "Equity",
        "type": "equity",
        "children": [
            {"code": "3100", "name": "Capital", "type": "equity"},
            {"code": "3200", "name": "Retained Earnings", "type": "equity"},
        ]
    },
    {
        "code": "4000",
        "name": "Income",
        "type": "income",
        "children": [
            {"code": "2100", "name": "Interest Income", "type": "income"},     # ✅ ADDED
            {"code": "4100", "name": "Interest Income", "type": "income"},     # existing
            {"code": "4200", "name": "Penalty Income", "type": "income"},
            {
                "code": "4300",
                "name": "Fee Income",
                "type": "income",
                "children": [
                    {"code": "4310", "name": "Loan Application Fee", "type": "income"},
                    {"code": "4320", "name": "Membership Fee", "type": "income"},
                    {"code": "4330", "name": "Passbook Sales", "type": "income"},
                    {"code": "4340", "name": "Withdrawal Charges", "type": "income"},
                    {"code": "4350", "name": "Commission (MTN)", "type": "income"},
                    {"code": "4360", "name": "Commission (Airtel)", "type": "income"},
                    {"code": "4370", "name": "Passport Photos", "type": "income"},
                    {"code": "4380", "name": "Printing & Photocopy", "type": "income"},
                ]
            }
        ]
    },
    {
        "code": "5000",
        "name": "Expenses",
        "type": "expense",
        "children": [
            {"code": "2000", "name": "Savings Withdrawal", "type": "expense"}, # ✅ ADDED
            {
                "code": "5100",
                "name": "Staff Costs",
                "type": "expense",
                "children": [
                    {"code": "5110", "name": "Salaries", "type": "expense"},
                    {"code": "5120", "name": "Staff Welfare", "type": "expense"},
                    {"code": "5130", "name": "Staff Rent", "type": "expense"},
                    {"code": "5140", "name": "Directors Drawings", "type": "expense"},
                ]
            },
            {
                "code": "5200",
                "name": "Operating Expenses",
                "type": "expense",
                "children": [
                    {"code": "5210", "name": "Office Rent", "type": "expense"},
                    {"code": "5220", "name": "Office Expenses", "type": "expense"},
                    {"code": "5230", "name": "Stationery", "type": "expense"},
                    {"code": "5240", "name": "Airtime", "type": "expense"},
                    {"code": "5250", "name": "Fuel for Recovery", "type": "expense"},
                    {"code": "5260", "name": "Motorcycle Expenses", "type": "expense"},
                    {"code": "5270", "name": "Transport Refund", "type": "expense"},
                ]
            },
            {
                "code": "5300",
                "name": "Financial Costs",
                "type": "expense",
                "children": [
                    {"code": "5310", "name": "Cash to Bank", "type": "expense"},
                    {"code": "5320", "name": "Cash Disbursed", "type": "expense"},
                ]
            }
        ]
    }
]


def create_accounts(nodes, parent=None):
    """Recursively create or update accounts from the structure."""
    for node in nodes:
        code = node["code"]
        name = node["name"]
        acc_type = node["type"]

        # Use update_or_create to handle existing accounts
        account, created = ChartOfAccount.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "account_type": acc_type,
                "parent": parent,
                "is_active": True,
            }
        )
        if created:
            print(f"✅ Created account {code} - {name}")
        else:
            print(f"🔄 Updated account {code} - {name}")

        # Recurse into children
        if "children" in node:
            create_accounts(node["children"], parent=account)


if __name__ == "__main__":
    print("🚀 Setting up corrected Chart of Accounts...")
    with transaction.atomic():
        # Deactivate all existing accounts to avoid duplicates? 
        # If you want to keep existing ones, comment out the next line.
        # ChartOfAccount.objects.all().update(is_active=False)
        create_accounts(COA_STRUCTURE)
    print("✅ Chart of Accounts setup complete.")