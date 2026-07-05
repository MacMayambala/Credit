import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User
from members.models import Member
from finance.models import SavingsAccount, Loan, Installment, Transaction

class DataMigrationService:
    """
    Deconstructs, validates, and migrates complete SACCO historical datasets.
    Maintains rigorous financial ledgers and ledger balance calculations.
    """
    REQUIRED_HEADERS = {
        "member_number",
        "first_name",
        "last_name",
        "gender",
        "date_of_birth",
        "nin",
        "phone_number",
        "savings_balance",
    }
    # ==============================
    # REQUIRED HEADERS (CORE ONLY)
    # ==============================
    TEMPLATE_HEADERS_ORDERED = [
    # Member
    "member_number",
    "first_name",
    "last_name",
    "gender",
    "date_of_birth",
    "nin",
    "card_number",
    "phone_number",
    "alternative_phone",
    "email",
    "physical_address",
    "village",
    "parish",
    "district",

    # Savings
    "savings_balance",

    # Loan
    "loan_reference",
    "principal_amount",
    "interest_rate",
    "period_months",
    "loan_start_date",
    "principal_balance",
    "interest_balance",
    "product_type",
    "loan_purpose",

    # Guarantors
    "guarantor_1_name",
    "guarantor_1_phone",

    # ======================
    # 🔥 PENALTY FIELDS (ADD THIS)
    # ======================
    "penalty_type",
    "penalty_rate",
    "penalty_flat_amount",
    "penalty_grace_days",
]
    @classmethod
    def _load_file_safely(cls, file_obj) -> pd.DataFrame:
        """
        Detects instruction banner row and normalizes headers.
        """
        name = getattr(file_obj, 'name', '').lower()

        if name.endswith(('.xlsx', '.xls')):
            df_check = pd.read_excel(file_obj, nrows=1, header=None)
            file_obj.seek(0)

            if not df_check.empty and "INSTRUCTIONS" in str(df_check.iloc[0, 0]):
                df = pd.read_excel(file_obj, skiprows=1)
            else:
                df = pd.read_excel(file_obj)
        else:
            first_line = file_obj.readline()
            if isinstance(first_line, bytes):
                first_line = first_line.decode('utf-8', errors='ignore')
            file_obj.seek(0)

            if "INSTRUCTIONS" in first_line:
                df = pd.read_csv(file_obj, skiprows=1)
            else:
                df = pd.read_csv(file_obj)

        df.columns = [str(c).strip().lower() for c in df.columns]
        return df

    @classmethod
    def validate_template_structure(cls, df: pd.DataFrame) -> list:
        """
        Ensures required columns exist (optional columns ignored).
        """
        missing = cls.REQUIRED_HEADERS - set(df.columns)
        return [f"Missing required column header: '{col}'" for col in missing]

    @classmethod
    def clean_nan(cls, val, default=None):
        if pd.isna(val) or val is np.nan or str(val).strip().lower() in ['nan', 'nat', 'null', '']:
            return default
        return str(val).strip()

    @classmethod
    def clean_decimal(cls, val) -> Decimal:
        cleaned = cls.clean_nan(val, '0.00')
        cleaned = cleaned.replace(',', '')
        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal('0.00')

    @classmethod
    def clean_date(cls, val):
        if pd.isna(val) or str(val).strip() == '':
            return None
        if isinstance(val, (datetime, pd.Timestamp)):
            return val.date()
        try:
            return pd.to_datetime(val).date()
        except Exception:
            return None

    @classmethod
    def preview_file(cls, file_obj) -> dict:
        try:
            df = cls._load_file_safely(file_obj)
        except Exception as e:
            return {"errors": [f"Unreadable file system matrix: {str(e)}"], "rows": []}

        errors = cls.validate_template_structure(df)
        if errors:
            return {"errors": errors, "rows": []}

        preview_rows = []

        for index, row in df.iterrows():
            if not cls.clean_nan(row.get('first_name')) and not cls.clean_nan(row.get('last_name')):
                continue

            preview_rows.append({
                "row_index": index + 2,
                "member_number": cls.clean_nan(row.get('member_number')),
                "name": f"{cls.clean_nan(row.get('first_name'), '')} {cls.clean_nan(row.get('last_name'), '')}",
                "nin": cls.clean_nan(row.get('nin')),
                "savings_balance": float(cls.clean_decimal(row.get('savings_balance'))),
                "loan_reference": cls.clean_nan(row.get('loan_reference')),
                "principal": float(cls.clean_decimal(row.get('principal_amount')))
            })

        return {"errors": [], "rows": preview_rows}

    @classmethod
    def execute_import(cls, file_obj, user: User) -> dict:
        report = {
            "success": True,
            "stats": {"members": 0, "savings": Decimal('0.00'), "loans": 0, "failed_rows": 0},
            "logs": []
        }

        try:
            df = cls._load_file_safely(file_obj)
        except Exception as e:
            report["success"] = False
            report["logs"].append(f"Critical error reading file: {str(e)}")
            return report

        for index, row in df.iterrows():
            row_num = index + 2

            if not cls.clean_nan(row.get('first_name')) and not cls.clean_nan(row.get('last_name')):
                continue

            try:
                with transaction.atomic():

                    member_num = cls.clean_nan(row.get('member_number'))
                    nin_val = cls.clean_nan(row.get('nin'))
                    first_name = cls.clean_nan(row.get('first_name'))
                    last_name = cls.clean_nan(row.get('last_name'))

                    if not first_name or not last_name:
                        raise ValueError("First name and Last name are required.")

                    if member_num and Member.objects.filter(member_number=member_num).exists():
                        raise ValueError(f"Duplicate Member: '{member_num}'")
                    if nin_val and Member.objects.filter(nin=nin_val).exists():
                        raise ValueError(f"Duplicate NIN: '{nin_val}'")

                    # ==============================
                    # CREATE MEMBER
                    # ==============================
                    member = Member(
                        first_name=first_name,
                        last_name=last_name,
                        gender=cls.clean_nan(row.get('gender'), 'Male'),
                        dob=cls.clean_date(row.get('date_of_birth')),
                        nin=nin_val,
                        card_number=cls.clean_nan(row.get('card_number')),
                        phone_number=cls.clean_nan(row.get('phone_number'), '0000000000'),
                        alternative_phone=cls.clean_nan(row.get('alternative_phone')),
                        email=cls.clean_nan(row.get('email')),
                        physical_address=cls.clean_nan(row.get('physical_address')),
                        village=cls.clean_nan(row.get('village')),
                        parish=cls.clean_nan(row.get('parish')),
                        district=cls.clean_nan(row.get('district'))
                    )

                    if member_num:
                        member.member_number = member_num

                    member.save()

                    # ==============================
                    # SAVINGS
                    # ==============================
                    savings_bal = cls.clean_decimal(row.get('savings_balance'))
                    savings_acc, _ = SavingsAccount.objects.get_or_create(member=member)

                    if savings_bal > 0:
                        savings_acc.balance = savings_bal
                        savings_acc.save()

                        Transaction.objects.create(
                            member=member,
                            amount=savings_bal,
                            type='deposit',
                            reference=f"MIGRATION-OPBAL-{member.member_number}",
                            created_by=user,
                            timestamp=timezone.now()
                        )

                    # ==============================
                    # LOAN IMPORT
                    # ==============================
                    loan_ref = cls.clean_nan(row.get('loan_reference'))
                    principal = cls.clean_decimal(row.get('principal_amount'))

                    if loan_ref and principal > 0:

                        if Loan.objects.filter(loan_reference=loan_ref).exists():
                            raise ValueError(f"Loan '{loan_ref}' exists.")

                        period = int(float(cls.clean_nan(row.get('period_months'), 12)))
                        l_start_date = cls.clean_date(row.get('loan_start_date')) or timezone.now().date()

                        p_bal = cls.clean_decimal(row.get('principal_balance'))
                        i_bal = cls.clean_decimal(row.get('interest_balance'))
                        interest_rate = cls.clean_decimal(row.get('interest_rate'))

                        # ==============================
                        # PENALTY FIELDS (NEW)
                        # ==============================
                        penalty_type = cls.clean_nan(row.get('penalty_type'), 'daily_flat')
                        penalty_rate = cls.clean_decimal(row.get('penalty_rate'))
                        penalty_flat_amount = cls.clean_decimal(row.get('penalty_flat_amount'))
                        penalty_grace_days = int(float(cls.clean_nan(row.get('penalty_grace_days'), 0)))

                        guarantor_name = cls.clean_nan(row.get('guarantor_1_name'), 'Migration Placeholder')
                        guarantor_phone = cls.clean_nan(row.get('guarantor_1_phone'), '0000000000')

                        # ==============================
                        # CREATE LOAN
                        # ==============================
                        loan = Loan.objects.create(
                            member=member,
                            officer=user,
                            loan_reference=loan_ref,
                            principal_amount=principal,
                            interest_rate=interest_rate,
                            period_months=period,
                            start_date=l_start_date,
                            disbursed_date=l_start_date,
                            principal_balance=p_bal,
                            interest_balance=i_bal,
                            product_type=cls.clean_nan(row.get('product_type'), 'personal').lower(),
                            purpose=cls.clean_nan(row.get('loan_purpose')),
                            guarantor_1_name=guarantor_name,
                            guarantor_1_phone=guarantor_phone,

                            # PENALTY SYSTEM
                            penalty_type=penalty_type,
                            penalty_rate=penalty_rate,
                            penalty_flat_amount=penalty_flat_amount,
                            penalty_grace_days=penalty_grace_days,

                            status='approved' if (p_bal > 0 or i_bal > 0) else 'closed',
                            is_active=True if p_bal > 0 else False
                        )

                        # INSTALLMENT SNAPSHOT
                        if p_bal > 0 or i_bal > 0:
                            Installment.objects.create(
                                loan=loan,
                                due_date=l_start_date,
                                principal_portion=p_bal,
                                interest_portion=i_bal,
                                penalty_amount=Decimal("0.00"),
                                principal_paid=Decimal("0.00"),
                                interest_paid=Decimal("0.00"),
                                penalty_paid=Decimal("0.00"),
                            )

                        # DISBURSEMENT TRANSACTION
                        Transaction.objects.create(
                            member=member,
                            loan=loan,
                            amount=principal,
                            type='disbursement',
                            reference=f"MIGRATION-DISB-{loan_ref}",
                            created_by=user,
                            timestamp=timezone.make_aware(
                                datetime.combine(l_start_date, datetime.min.time())
                            )
                        )

                        report["stats"]["loans"] += 1

                report["stats"]["members"] += 1
                report["stats"]["savings"] += savings_bal
                report["logs"].append(f"Row {row_num}: Imported {member.member_number}")

            except Exception as row_error:
                report["stats"]["failed_rows"] += 1
                report["logs"].append(f"Row {row_num}: Failed - {str(row_error)}")

        return report