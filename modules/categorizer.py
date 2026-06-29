"""Categorize fictional Alex Rivera transactions into CFO-level categories."""

from pathlib import Path

import pandas as pd

from modules.config import APPROVED_CATEGORIES
from modules.validation import validate_transactions_for_processing

CATEGORIES = APPROVED_CATEGORIES

CONFIDENCE_THRESHOLD = 0.70


EXACT_VENDOR_MATCHES = {
    "PARKSIDE RENT PORTAL": "Housing",
    "PAYROLL DEPOSIT": "Income",
    "NETFLIX": "Subscriptions",
    "SPOTIFY": "Subscriptions",
    "HULU": "Subscriptions",
    "VERIZON WIRELESS": "Subscriptions",
    "CITYFIT GYM": "Subscriptions",
    "TRADER JOE'S": "Food & Dining",
    "WHOLE FOODS MARKET": "Food & Dining",
    "SAFEWAY": "Food & Dining",
    "BLUE BOTTLE COFFEE": "Food & Dining",
    "SWEETGREEN": "Food & Dining",
    "CHIPOTLE": "Food & Dining",
    "LOCAL TAQUERIA": "Food & Dining",
    "RAMEN HOUSE": "Food & Dining",
    "DOORDASH THAI GARDEN": "Food & Dining",
    "PHILZ COFFEE": "Food & Dining",
    "NEIGHBORHOOD PIZZA": "Food & Dining",
    "BRUNCH CAFE": "Food & Dining",
    "SUSHI SPOT": "Food & Dining",
    "UBER EATS BURGER BAR": "Food & Dining",
    "LYFT": "Transport",
    "UBER": "Transport",
    "FEDERAL STUDENT LOAN SERVICER": "Education",
    "ZARA": "Shopping",
    "GAP FLAGSHIP STORE": "Shopping",
    "UNIQLO": "Shopping",
    "H&M": "Shopping",
    "TARGET": "Shopping",
    "APPLE STORE REPAIR": "Shopping",
    "WALGREENS": "Medical",
    "DENTIST COPAY": "Medical",
    "AUTO REGISTRATION RENEWAL": "Transport",
}


KEYWORD_MATCHES = [
    ("UBER EATS", "Food & Dining"),
    ("DOORDASH", "Food & Dining"),
    ("UBER", "Transport"),
    ("LYFT", "Transport"),
    ("VENMO FROM", "Income"),
    ("PAYROLL", "Income"),
    ("RENT", "Housing"),
    ("LOAN", "Education"),
    ("STUDENT", "Education"),
    ("DENTIST", "Medical"),
    ("WALGREENS", "Medical"),
    ("GYM", "Subscriptions"),
    ("NETFLIX", "Subscriptions"),
    ("SPOTIFY", "Subscriptions"),
    ("HULU", "Subscriptions"),
    ("VERIZON", "Subscriptions"),
    ("WHOLE FOODS", "Food & Dining"),
    ("TRADER JOE", "Food & Dining"),
    ("SAFEWAY", "Food & Dining"),
    ("COFFEE", "Food & Dining"),
    ("CAFE", "Food & Dining"),
    ("PIZZA", "Food & Dining"),
    ("SUSHI", "Food & Dining"),
    ("RAMEN", "Food & Dining"),
    ("TAQUERIA", "Food & Dining"),
    ("SWEETGREEN", "Food & Dining"),
    ("CHIPOTLE", "Food & Dining"),
    ("ZARA", "Shopping"),
    ("GAP", "Shopping"),
    ("UNIQLO", "Shopping"),
    ("H&M", "Shopping"),
    ("TARGET", "Shopping"),
    ("APPLE STORE", "Shopping"),
    ("REGISTRATION", "Transport"),
]


# Broad, real-world merchant and keyword library so a normal person's vendors
# categorize well instead of falling to "Misc". Checked AFTER the sample-persona
# rules above (so Alex's categorization is unchanged) and BEFORE the Misc
# fallback. Ordered so more distinctive/less-ambiguous terms win first when two
# could match the same vendor (e.g. "MARKETPLACE" -> Shopping before grocery
# terms). This list is intentionally transparent and human-editable.
GENERAL_KEYWORD_MATCHES = [
    # Savings / investing transfers (distinctive brokerage names first)
    ("VANGUARD", "Savings Transfer"),
    ("FIDELITY", "Savings Transfer"),
    ("CHARLES SCHWAB", "Savings Transfer"),
    ("SCHWAB", "Savings Transfer"),
    ("ROBINHOOD", "Savings Transfer"),
    ("COINBASE", "Savings Transfer"),
    ("BETTERMENT", "Savings Transfer"),
    ("WEALTHFRONT", "Savings Transfer"),
    ("ACORNS", "Savings Transfer"),
    ("401K", "Savings Transfer"),
    ("ROTH IRA", "Savings Transfer"),
    ("TRANSFER TO SAVINGS", "Savings Transfer"),
    ("HIGH YIELD SAVINGS", "Savings Transfer"),
    ("HIGH-YIELD SAVINGS", "Savings Transfer"),
    # Shopping (put MARKETPLACE before any grocery term to avoid mis-bucketing)
    ("AMAZON MKTP", "Shopping"),
    ("AMAZON MARKETPLACE", "Shopping"),
    ("MARKETPLACE", "Shopping"),
    ("AMAZON", "Shopping"),
    ("WALMART", "Shopping"),
    ("BEST BUY", "Shopping"),
    ("HOME DEPOT", "Shopping"),
    ("LOWE'S", "Shopping"),
    ("IKEA", "Shopping"),
    ("MACY'S", "Shopping"),
    ("NORDSTROM", "Shopping"),
    ("KOHL'S", "Shopping"),
    ("WAYFAIR", "Shopping"),
    ("ETSY", "Shopping"),
    ("EBAY", "Shopping"),
    ("SEPHORA", "Shopping"),
    ("ULTA", "Shopping"),
    ("NIKE", "Shopping"),
    ("LULULEMON", "Shopping"),
    ("SHEIN", "Shopping"),
    ("TEMU", "Shopping"),
    ("BED BATH", "Shopping"),
    # Subscriptions, streaming, utilities, insurance, phone, internet
    ("DISNEY PLUS", "Subscriptions"),
    ("DISNEY+", "Subscriptions"),
    ("HBO MAX", "Subscriptions"),
    ("PRIME VIDEO", "Subscriptions"),
    ("YOUTUBE PREMIUM", "Subscriptions"),
    ("APPLE.COM/BILL", "Subscriptions"),
    ("ICLOUD", "Subscriptions"),
    ("GOOGLE STORAGE", "Subscriptions"),
    ("DROPBOX", "Subscriptions"),
    ("ADOBE", "Subscriptions"),
    ("MICROSOFT 365", "Subscriptions"),
    ("PATREON", "Subscriptions"),
    ("SUBSTACK", "Subscriptions"),
    ("PELOTON", "Subscriptions"),
    ("PLANET FITNESS", "Subscriptions"),
    ("FITNESS", "Subscriptions"),
    ("INSURANCE", "Subscriptions"),
    ("GEICO", "Subscriptions"),
    ("STATE FARM", "Subscriptions"),
    ("PROGRESSIVE", "Subscriptions"),
    ("ALLSTATE", "Subscriptions"),
    ("COMCAST", "Subscriptions"),
    ("XFINITY", "Subscriptions"),
    ("SPECTRUM", "Subscriptions"),
    ("T-MOBILE", "Subscriptions"),
    ("AT&T", "Subscriptions"),
    ("CRICKET WIRELESS", "Subscriptions"),
    ("ELECTRIC", "Subscriptions"),
    ("PACIFIC GAS", "Subscriptions"),
    ("PG&E", "Subscriptions"),
    ("CON EDISON", "Subscriptions"),
    ("DUKE ENERGY", "Subscriptions"),
    ("UTILITY", "Subscriptions"),
    ("WATER DISTRICT", "Subscriptions"),
    ("INTERNET", "Subscriptions"),
    ("CHILDCARE", "Education"),
    ("DAYCARE", "Education"),
    ("529 PLAN", "Education"),
    # Housing
    ("MORTGAGE", "Housing"),
    ("APARTMENT", "Housing"),
    ("PROPERTY MANAGEMENT", "Housing"),
    ("PROPERTY MGMT", "Housing"),
    ("REALTY", "Housing"),
    ("LEASING", "Housing"),
    ("LANDLORD", "Housing"),
    ("HOA", "Housing"),
    ("PROPERTY TAX", "Housing"),
    ("ESCROW", "Housing"),
    ("PLUMBING", "Housing"),
    ("APPLIANCE", "Housing"),
    ("ZILLOW", "Housing"),
    # Transport (gas stations, transit, air, auto)
    ("SHELL", "Transport"),
    ("CHEVRON", "Transport"),
    ("EXXON", "Transport"),
    ("MOBIL", "Transport"),
    ("ARCO", "Transport"),
    ("TEXACO", "Transport"),
    ("CITGO", "Transport"),
    ("VALERO", "Transport"),
    ("SUNOCO", "Transport"),
    ("GAS STATION", "Transport"),
    ("FUEL", "Transport"),
    ("PARKING", "Transport"),
    ("TOLL", "Transport"),
    ("TRANSIT", "Transport"),
    ("METRO", "Transport"),
    ("CALTRAIN", "Transport"),
    ("AMTRAK", "Transport"),
    ("AIRLINE", "Transport"),
    ("AIR LINES", "Transport"),
    ("SOUTHWEST", "Transport"),
    ("TRAVEL", "Transport"),
    ("CAR WASH", "Transport"),
    ("JIFFY LUBE", "Transport"),
    ("AUTOZONE", "Transport"),
    ("DMV", "Transport"),
    ("AUTO LOAN", "Transport"),
    ("AUTO FINANCE", "Transport"),
    ("FINANCIAL SERVICES", "Transport"),
    ("MOTOR CREDIT", "Transport"),
    # Medical
    ("PHARMACY", "Medical"),
    ("CVS", "Medical"),
    ("RITE AID", "Medical"),
    ("DENTAL", "Medical"),
    ("DENTIST", "Medical"),
    ("ORTHODONT", "Medical"),
    ("PEDIATRIC", "Medical"),
    ("COPAY", "Medical"),
    ("CLINIC", "Medical"),
    ("HOSPITAL", "Medical"),
    ("URGENT CARE", "Medical"),
    ("MEDICAL", "Medical"),
    ("OPTOMETRY", "Medical"),
    ("LABCORP", "Medical"),
    ("QUEST DIAGNOSTIC", "Medical"),
    # Education
    ("TUITION", "Education"),
    ("UNIVERSITY", "Education"),
    ("COLLEGE", "Education"),
    ("COURSERA", "Education"),
    ("UDEMY", "Education"),
    ("TEXTBOOK", "Education"),
    ("BOOKSTORE", "Education"),
    # Entertainment
    ("MOVIE", "Entertainment"),
    ("THEATER", "Entertainment"),
    ("THEATRE", "Entertainment"),
    ("TICKETMASTER", "Entertainment"),
    ("STUBHUB", "Entertainment"),
    ("FANDANGO", "Entertainment"),
    ("AMC ", "Entertainment"),
    ("REGAL", "Entertainment"),
    ("STEAM GAMES", "Entertainment"),
    ("PLAYSTATION", "Entertainment"),
    ("XBOX", "Entertainment"),
    ("NINTENDO", "Entertainment"),
    ("CONCERT", "Entertainment"),
    ("MUSEUM", "Entertainment"),
    # Food & Dining (grocery chains, then dining keywords)
    ("COSTCO", "Food & Dining"),
    ("KROGER", "Food & Dining"),
    ("ALDI", "Food & Dining"),
    ("PUBLIX", "Food & Dining"),
    ("WEGMANS", "Food & Dining"),
    ("VONS", "Food & Dining"),
    ("RALPHS", "Food & Dining"),
    ("ALBERTSONS", "Food & Dining"),
    ("FOOD LION", "Food & Dining"),
    ("MEIJER", "Food & Dining"),
    ("H-E-B", "Food & Dining"),
    ("INSTACART", "Food & Dining"),
    ("GROCERY", "Food & Dining"),
    ("SUPERMARKET", "Food & Dining"),
    ("STARBUCKS", "Food & Dining"),
    ("MCDONALD", "Food & Dining"),
    ("WENDY'S", "Food & Dining"),
    ("DUNKIN", "Food & Dining"),
    ("PANERA", "Food & Dining"),
    ("GRUBHUB", "Food & Dining"),
    ("RESTAURANT", "Food & Dining"),
    ("GRILL", "Food & Dining"),
    ("KITCHEN", "Food & Dining"),
    ("TACO", "Food & Dining"),
    ("BURGER", "Food & Dining"),
    ("BAKERY", "Food & Dining"),
    ("DELI", "Food & Dining"),
    ("DINER", "Food & Dining"),
    ("BISTRO", "Food & Dining"),
    ("BREWERY", "Food & Dining"),
    # Income signals (genuine earnings; refunds handled separately in classify)
    ("PAYROLL", "Income"),
    ("DIRECT DEPOSIT", "Income"),
    ("DIRECT DEP", "Income"),
    ("PAYCHECK", "Income"),
    ("SALARY", "Income"),
    ("INVOICE", "Income"),
    ("CLIENT PAYMENT", "Income"),
    ("ZELLE FROM", "Income"),
]


RAW_CATEGORY_TRUTH_MAP = {
    "rent": "Housing",
    "groceries": "Food & Dining",
    "dining": "Food & Dining",
    "transportation": "Transport",
    "subscription": "Subscriptions",
    "gym": "Subscriptions",
    "income": "Income",
    "transfer": "Income",
    "student_loan": "Education",
    "health": "Medical",
    "medical": "Medical",
    "clothing": "Shopping",
    "household": "Shopping",
    "shopping": "Shopping",
    "entertainment": "Entertainment",
    "education": "Education",
    "phone": "Subscriptions",
    "unusual": "Shopping",
    "mortgage": "Housing",
    "housing": "Housing",
    "utilities": "Subscriptions",
    "insurance": "Subscriptions",
    "internet": "Subscriptions",
    "childcare": "Education",
    "auto_loan": "Transport",
    "investment": "Savings Transfer",
    "savings": "Savings Transfer",
    "travel": "Transport",
    "home_repair": "Housing",
}

EXPECTED_VENDOR_OVERRIDES = {
    "DENTIST COPAY": "Medical",
    "AUTO REGISTRATION RENEWAL": "Transport",
    "APPLE STORE REPAIR": "Shopping",
}


def normalize_vendor(vendor):
    """Make vendor names easier to compare reliably."""
    return str(vendor).strip().upper()


REFUND_SIGNALS = ("REFUND", "REVERSAL", "CASHBACK", "RETURN")


def classify(vendor, amount=None):
    """Return a local best-guess category and confidence for unmatched vendors."""
    normalized_vendor = normalize_vendor(vendor)
    amount = float(amount) if amount is not None else 0.0

    if amount > 0:
        # A positive amount is income by default, unless the vendor signals a
        # refund/credit. Refunds are not earnings; bucketing them as Misc keeps
        # them out of the income total so savings rate is not inflated.
        if any(signal in normalized_vendor for signal in REFUND_SIGNALS):
            return "Misc", 0.75
        return "Income", 0.80

    if "SAVE" in normalized_vendor or "BROKERAGE" in normalized_vendor:
        return "Savings Transfer", 0.80

    if "TICKET" in normalized_vendor or "CINEMA" in normalized_vendor:
        return "Entertainment", 0.75

    return "Misc", 0.50


def categorize_transaction(row):
    """Apply exact, keyword, local classifier, then unknown bucket rules."""
    vendor = normalize_vendor(row["vendor"])
    amount = row.get("amount")

    if vendor in EXACT_VENDOR_MATCHES:
        return pd.Series(
            {
                "assigned_category": EXACT_VENDOR_MATCHES[vendor],
                "classification_method": "exact_vendor_match",
            }
        )

    for keyword, category in KEYWORD_MATCHES:
        if keyword in vendor:
            return pd.Series(
                {
                    "assigned_category": category,
                    "classification_method": "keyword_match",
                }
            )

    # Refund-signalled positives are credits, not income or a merchant purchase;
    # let classify() bucket them before a general merchant keyword mislabels them.
    is_refund = (amount is not None and float(amount) > 0
                 and any(signal in vendor for signal in REFUND_SIGNALS))
    if not is_refund:
        for keyword, category in GENERAL_KEYWORD_MATCHES:
            if keyword in vendor:
                return pd.Series(
                    {
                        "assigned_category": category,
                        "classification_method": "general_keyword_match",
                    }
                )

    category, confidence = classify(vendor, amount)
    if confidence >= CONFIDENCE_THRESHOLD:
        return pd.Series(
            {
                "assigned_category": category,
                "classification_method": f"ai_assisted_fallback_{confidence:.2f}",
            }
        )

    return pd.Series(
        {
            "assigned_category": "Misc",
            "classification_method": f"unknown_below_{CONFIDENCE_THRESHOLD:.2f}",
        }
    )


def calculate_accuracy(df):
    """Compare assigned categories against the fictional raw-category truth map."""
    expected_categories = df["raw_category"].map(RAW_CATEGORY_TRUTH_MAP)
    vendor_overrides = df["vendor"].map(
        lambda vendor: EXPECTED_VENDOR_OVERRIDES.get(normalize_vendor(vendor))
    )
    # combine_first prefers the vendor override and falls back to the raw-category
    # map; it avoids the deprecated object-dtype downcast that .fillna warns about.
    expected_categories = vendor_overrides.combine_first(expected_categories)
    matches = df["assigned_category"] == expected_categories
    return matches.mean() * 100


def categorize_file(input_path, output_path):
    """Read the raw CSV, categorize each row, and save a new categorized CSV."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    df = pd.read_csv(input_path)
    df = validate_transactions_for_processing(df)
    classification_columns = df.apply(categorize_transaction, axis=1)
    categorized_df = pd.concat([df, classification_columns], axis=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    categorized_df.to_csv(output_path, index=False)

    accuracy_rate = calculate_accuracy(categorized_df)
    return categorized_df, accuracy_rate
