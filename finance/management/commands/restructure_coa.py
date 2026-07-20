from django.core.management.base import BaseCommand
from django.db import transaction
from finance.models import ChartOfAccount

class Command(BaseCommand):
    help = "Restructures the Chart of Accounts into a hierarchical system"

    def handle(self, *args, **options):
        # Step 1: Deactivate all existing accounts to avoid conflicts
        self.stdout.write("Deactivating existing accounts...")
        ChartOfAccount.objects.all().update(is_active=False)

        # Step 2: Define the new COA structure as nested dicts
        # Each entry: code, name, type, and children (list)
        coa_structure = [
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
                    {
                        "code": "2100",
                        "name": "Member Savings",
                        "type": "liability",
                    },
                    {
                        "code": "2200",
                        "name": "External Loans",
                        "type": "liability",
                    },
                    {
                        "code": "2300",
                        "name": "Accrued Expenses",
                        "type": "liability",
                    }
                ]
            },
            {
                "code": "3000",
                "name": "Equity",
                "type": "equity",
                "children": [
                    {
                        "code": "3100",
                        "name": "Capital",
                        "type": "equity",
                    },
                    {
                        "code": "3200",
                        "name": "Retained Earnings",
                        "type": "equity",
                    }
                ]
            },
            {
                "code": "4000",
                "name": "Income",
                "type": "income",
                "children": [
                    {
                        "code": "4100",
                        "name": "Interest Income",
                        "type": "income",
                    },
                    {
                        "code": "4200",
                        "name": "Penalty Income",
                        "type": "income",
                    },
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

        self.stdout.write("Creating new Chart of Accounts...")
        with transaction.atomic():
            self._create_accounts(coa_structure, parent=None)

        self.stdout.write(self.style.SUCCESS("COA restructuring completed successfully!"))

    def _create_accounts(self, nodes, parent):
        """Recursively create accounts from the nested structure."""
        for node in nodes:
            code = node["code"]
            name = node["name"]
            acc_type = node["type"]

            # Check if account already exists (shouldn't since we deactivated)
            account, created = ChartOfAccount.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "account_type": acc_type,
                    "parent": parent,
                    "is_active": True,
                }
            )
            if not created:
                # If it exists but is inactive, reactivate and update fields
                account.is_active = True
                account.name = name
                account.account_type = acc_type
                account.parent = parent
                account.save()

            # Recurse into children
            if "children" in node:
                self._create_accounts(node["children"], parent=account)